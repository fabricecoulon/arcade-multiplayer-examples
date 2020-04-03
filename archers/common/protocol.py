"""
Module for interacting on the network via a Async Protocol
"""
import asyncio
import logging
import os
from base64 import b64encode
from hashlib import sha1

import umsgpack


class MalformedMessage(Exception):
    pass


class Endpoint:

    def __init__(self, queue_size=None, logger=None):
        if queue_size is None:
            queue_size = 0
        self._queue = asyncio.Queue(queue_size)
        self._closed = False
        self._transport = None
        self._logger = logger or logging.getLogger(__name__)

    def feed_datagram(self, data, addr):
        try:
            self._queue.put_nowait((data, addr))
        except asyncio.QueueFull:
            warnings.warn('Endpoint queue is full')

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._queue.empty():
            self.feed_datagram(None, None)
        if self._transport:
            self._transport.close()

    def send(self, data, addr):
        if self._closed:
            raise IOError("Enpoint is closed")
        self._transport.sendto(data, addr)

    async def receive(self):
        if self._queue.empty() and self._closed:
            raise IOError("Enpoint is closed")
        data, addr = await self._queue.get()
        if data is None:
            raise IOError("Enpoint is closed")
        return data, addr

    def abort(self):
        if self._closed:
            raise IOError("Enpoint is closed")
        self._transport.abort()
        self.close()

    @property
    def address(self):
        return self._transport.get_extra_info("socket").getsockname()

    @property
    def closed(self):
        return self._closed

    @property
    def transport(self):
        return self._transport

    @transport.setter
    def transport(self, value):
        if self._transport:
            self._transport.close()
        self._transport = value


class LocalEndpoint(Endpoint):
    pass


class RemoteEndpoint(Endpoint):

    def send(self, data):
        """Send a datagram to the remote host."""
        super().send(data, None)

    async def receive(self):
        """ Wait for an incoming datagram from the remote host.

        This method is a coroutine.
        """
        data, addr = await super().receive()
        return data


class EndpointHelper:

    def __init__(self, protocol, post_connect, logger=None):
        self._protocol = protocol
        self._logger = logger or logging.getLogger(__name__)
        self._post_connect = post_connect

    async def _open_datagram_endpoint(self,
            host, port, *, endpoint_factory=Endpoint, remote=False, **kwargs):
        if not self._protocol:
            raise
        loop = asyncio.get_event_loop()
        endpoint = endpoint_factory()
        kwargs['remote_addr' if remote else 'local_addr'] = host, port
        if remote:
            self._logger.debug("remote_addr = %s" % str(kwargs['remote_addr']))
        else:
            self._logger.debug("local_addr = %s" % str(kwargs['local_addr']))
        kwargs['protocol_factory'] = lambda: self._protocol(endpoint)
        transport, protocol = await loop.create_datagram_endpoint(**kwargs)
        if self._post_connect:
            self._post_connect()
        return endpoint, protocol


    async def open_local_endpoint(self,
            host='0.0.0.0', port=0, *, queue_size=None, **kwargs):
        if not self._protocol:
            raise
        return await self._open_datagram_endpoint(
            host, port, remote=False,
            endpoint_factory=lambda: LocalEndpoint(queue_size),
            **kwargs)

    async def open_remote_endpoint(self,
            host, port, *, queue_size=None, **kwargs):
        if not self._protocol:
            raise
        return await self._open_datagram_endpoint(
            host, port, remote=True,
            endpoint_factory=lambda: RemoteEndpoint(queue_size),
            **kwargs)

class RPCProtocol(asyncio.DatagramProtocol):

    def __init__(self, endpoint, logger=None, wait_timeout=5):
        self._endpoint = endpoint
        self._wait_timeout = wait_timeout
        self._outstanding = {}
        self._logger = logger or logging.getLogger(__name__)

    def connection_made(self, transport):
        self._endpoint.transport = transport

    def datagram_received(self, data, addr):
        self._logger.debug("received datagram from %s", addr)
        asyncio.ensure_future(self._solve_datagram(data, addr))

    async def _solve_datagram(self, datagram, address):
        if len(datagram) < 22:
            self._logger.warning("received datagram too small from %s,"
                        " ignoring", address)
            return

        msg_id = datagram[1:21]
        data = umsgpack.unpackb(datagram[21:])

        if datagram[:1] == b'\x00':
            # schedule accepting request and returning the result
            asyncio.ensure_future(self._accept_request(msg_id, data, address))
        elif datagram[:1] == b'\x01':
            self._accept_response(msg_id, data, address)
        # Fire and forget mode
        elif datagram[:1] == b'\x02':
            # schedule accepting request and returning nothing
            asyncio.ensure_future(self._accept_request2(msg_id, data, address))
        else:
            # don't do anything
            self._logger.debug("Received unknown message from %s, ignoring", address)

    def _accept_response(self, msg_id, data, address):
        msgargs = (b64encode(msg_id), address)
        if msg_id not in self._outstanding:
            self._logger.warning("received unknown message %s "
                        "from %s; ignoring", *msgargs)
            return
        self._logger.debug("received response %s for message "
                  "id %s from %s", data, *msgargs)
        future, timeout = self._outstanding[msg_id]
        timeout.cancel()
        future.set_result((True, data))
        del self._outstanding[msg_id]

    async def _accept_request(self, msg_id, data, address):
        if not isinstance(data, list) or len(data) != 2:
            raise MalformedMessage("Could not read packet: %s" % data)
        funcname, args = data
        func = getattr(self, "rpc_%s" % funcname, None)
        if func is None or not callable(func):
            msgargs = (self.__class__.__name__, funcname)
            self._logger.warning("%s has no callable method "
                        "rpc_%s; ignoring request", *msgargs)
            return

        if not asyncio.iscoroutinefunction(func):
            func = asyncio.coroutine(func)
        response = await func(address, *args)
        self._logger.debug("sending response %s for msg id %s to %s",
                  response, b64encode(msg_id), address)
        txdata = b'\x01' + msg_id + umsgpack.packb(response)
        self._endpoint.send(txdata, address)

    async def _accept_request2(self, msg_id, data, address):
        if not isinstance(data, list) or len(data) != 2:
            raise MalformedMessage("Could not read packet: %s" % data)
        funcname, args = data
        # Fire and forget mode
        func = getattr(self, "rpc_%s" % funcname, None)
        if func is None or not callable(func):
            msgargs = (self.__class__.__name__, funcname)
            self._logger.warning("%s has no callable method "
                        "rpc_%s; ignoring request", *msgargs)
            return

        if not asyncio.iscoroutinefunction(func):
            func = asyncio.coroutine(func)
        response = await func(address, *args)

    def _timeout(self, msg_id):
        args = (b64encode(msg_id), self._wait_timeout)
        self._logger.error("Did not received reply for msg "
                  "id %s within %i seconds", *args)
        self._outstanding[msg_id][0].set_result((False, None))
        del self._outstanding[msg_id]

    def __getattr__(self, name):
        """
        If name begins with "_" or "rpc_", returns the value of
        the attribute in question as normal.

        Otherwise, returns the value as normal *if* the attribute
        exists, but does *not* raise AttributeError if it doesn't.

        Instead, returns a closure, func, which takes an argument
        "address" and additional arbitrary args (but not kwargs).

        func attempts to call a remote method "rpc_{name}",
        passing those args, on a node reachable at address.
        """
        if name.startswith("_") or name.startswith("rpc_"):
            return getattr(super(), name)

        try:
            return getattr(super(), name)
        except AttributeError:
            pass

        def func(address, *args):
            if name.startswith("ff_"):
                func_type = 0x02
            else:
                func_type = 0x00
            msg_id = sha1(os.urandom(32)).digest()
            data = umsgpack.packb([name, args])
            if len(data) > 8192:
                raise MalformedMessage("Total length of function "
                                       "name and arguments cannot exceed 8K")
            if func_type == 0x02:
                txdata = b'\x02' + msg_id + data
            else:
                txdata = b'\x00' + msg_id + data
            self._logger.debug("calling remote function %s on %s (msgid %s)",
                      name, address, b64encode(msg_id))
            self._endpoint.send(txdata)

            if func_type != 0x02:
                loop = asyncio.get_event_loop()
                if hasattr(loop, 'create_future'):
                    future = loop.create_future()
                else:
                    future = asyncio.Future()
                timeout = loop.call_later(self._wait_timeout,
                                          self._timeout, msg_id)
                self._outstanding[msg_id] = (future, timeout)
                return future
            else:
                return

        return func
