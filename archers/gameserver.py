#!/usr/bin/env python
import logging
import asyncio
import time
import random
from common.protocol import EndpointHelper, RPCProtocol
from common.helpers import MOVE_MAP, apply_movement, MeasureDuration
from common.vector2 import Vector2
from common.datacls import PlayerData, GameData, Event, ProjectileData
from dataclasses import asdict
from collections import deque
from common.helpers import TOPIC_NEWPLAYER, PROJECTILE

LOG = logging.getLogger('gameserver')

#LOGLEVEL = logging.INFO
#LOGLEVEL = logging.DEBUG
LOGLEVEL = logging.ERROR

SERVER_TICKRATE = 1/60
#SERVER_TICKRATE = 1/30

WWIDTH = 800
WHEIGHT = 600

class PlayerClientInfo:
    def __init__(self, playerid, addr, endpoint=None, protocol=None):
        self.playerid = playerid
        if not isinstance(addr, tuple):
            raise Exception('addr must be a tuple')
        self.addr = addr
        self.endpoint = endpoint
        self.protocol = protocol
        self.ready = False



class RPCServerProtocol(RPCProtocol):
    gs_state = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._count = 0

    @classmethod
    def set_server_state(cls, value):
        if cls.gs_state is None:
            cls.gs_state = value
            return
        else:
            raise

    def rpc_ff_set_player_state(self, sender, player_state):
        if self.gs_state is None:
            raise
        self._count += 1
        if (self._count > 1000):
            self._count = 0
        LOG.info("RPCServer received: [%s], from %s:%i" % (player_state, sender[0], sender[1]))
        _, p = self.gs_state.game_state.get_player_from_id(player_state['id'])
        p.keys_pressed = player_state['keys_pressed'].copy()
        p.speed = player_state['speed']
        self.gs_state.game_state.updated_at = time.time()
        return

    def rpc_create_player(self, sender, player_id, player_port):
        if self.gs_state is None:
            raise
        LOG.info("RPCServer received: [%s], from %s:%i" % (player_id, sender[0], sender[1]))
        _player_remote_addr = (sender[0], player_port)
        p = PlayerClientInfo(player_id, _player_remote_addr)
        self.gs_state.server_state.remotes.append(p)
        rand_pos = [random.randint(100, WWIDTH), random.randint(100, WHEIGHT)]
        player = PlayerData(id=player_id, ts=time.time(), position=rand_pos, keys_pressed={}, speed=0)
        self.gs_state.game_state.players.append(player)
        LOG.info('nb players = %d' % len(self.gs_state.game_state.players))

        self.gs_state.server_state.eventq.append(Event(self._count, time.time(), TOPIC_NEWPLAYER, (player_id,)))

        return asdict(player)

    def rpc_delete_player(self, sender, player_id):
        if self.gs_state is None:
            raise
        LOG.info("RPCServer received: [%s], from %s:%i" % (player_id, sender[0], sender[1]))
        for i, p in enumerate(self.gs_state.server_state.remotes):
            if p.playerid == player_id:
                del(self.gs_state.server_state.remotes[i])
                idx, p = self.gs_state.game_state.get_player_from_id(player_id)
                del(self.gs_state.game_state.players[idx])
                LOG.info('Player %d removed' % player_id)
                break
        else:
            return False
        return True

    def rpc_get_player_state(self, sender, player_id):
        if self.gs_state is None:
            raise
        res = None
        idx, p = self.gs_state.game_state.get_player_from_id(player_id)
        if p:
            res = p.position
        return res

    def rpc_get_game_state(self, sender):
        if self.gs_state is None:
            raise
        return asdict(self.gs_state.game_state)

    def rpc_ff_process_client_events(self, sender, data):
        if self.gs_state is None or not data['params'][0]:
            raise RuntimeError('Not supposed to happend')
        obj_meta_data = data['params'][0]
        #print(obj_meta_data)
        if obj_meta_data['klass'] == PROJECTILE:
            projectile = ProjectileData(**obj_meta_data['obj_as_dict'])
            print(projectile)

class ServerState:
    def __init__(self, game_state):
        self._running = False
        self.local_addr = ('0.0.0.0', 1234)
        self.default_remote_addr_port = 4321
        self.remotes = []  # for server to client(s) publish_game_state
        self.local_endpoint = None
        self._count = 0
        self.eventq = deque()
        self._game_state = game_state

    @property
    def running(self):
        return self._running
    @running.setter
    def running(self, value):
        self._running = value

    def stop(self):
        if not self._running:
            return
        if self.local_endpoint:
            self.local_endpoint.close()
            self.local_endpoint = None
        self._running = False

    def update(self):
        if len(self._game_state.players) == 0:
            return
        self._count += 1
        _last_update = self._game_state.updated_at
        dt = time.time() - _last_update
        for p in self._game_state.players:
            if p.position and p.keys_pressed:
                curr_pos = Vector2(p.position)
                new_pos = apply_movement(p.speed, dt, curr_pos, p.keys_pressed)
                p.position = new_pos.as_list
                if ((self._count % 100) == 0):
                    LOG.debug('%d:' % p.id, ' p.pos:', p.position)
                    self._count = 0
                self._game_state.updated_at = time.time()

async def run_every_x_s(seconds, gs_state):
    i = 0
    while True:
        dur = 0
        with MeasureDuration() as m:
            gs_state.server_state.update()
        dur = seconds - m.duration
        if (i % 100) == 0:
            LOG.debug('seconds %f' % dur)
        i += 1
        await asyncio.sleep(dur)

async def init_local_endpoint(gs_state):
    endpoint_helper = EndpointHelper(RPCServerProtocol, lambda: RPCServerProtocol.set_server_state(gs_state))
    endpoint, _ = await endpoint_helper.open_local_endpoint(*gs_state.server_state.local_addr)
    return endpoint

async def init_remote_endpoint(remote_addr):
    endpoint_helper = EndpointHelper(RPCServerProtocol, None)
    LOG.info("init_remote_endpoint: %s" % str(remote_addr))
    endpoint, protocol = await endpoint_helper.open_remote_endpoint(*remote_addr)
    return endpoint, protocol

async def main(gs_state):
    local_endpoint = await init_local_endpoint(gs_state)
    LOG.info('Local endpoint created')
    gs_state.server_state.running = True
    gs_state.server_state.local_endpoint = local_endpoint
    await run_every_x_s(SERVER_TICKRATE, gs_state)

async def publish_game_state(gs_state):
    publish_state = True
    publish_event = True
    while True:

        # Publish game state
        for p in gs_state.server_state.remotes:

            if not p.ready:
                p.endpoint, p.protocol = await init_remote_endpoint(p.addr)
                LOG.info("#1 Remote endpoint (%d) created for player %d (%s)" % (id(p), p.playerid, p.addr))
                p.ready = True

            if publish_state and p.ready and gs_state.game_state:
                p.protocol.ff_listen_for_game_state_or_event(p.addr, asdict(gs_state.game_state))

        # Publish event(s)
        e = None
        if len(gs_state.server_state.eventq) > 0:
            e = gs_state.server_state.eventq.popleft()

        if e:
            for p in gs_state.server_state.remotes:
                if publish_event and p.ready:
                    p.protocol.ff_listen_for_game_state_or_event(p.addr, asdict(e))

        await asyncio.sleep(SERVER_TICKRATE)

class GameServerState:
    _instance = None

    def __init__(self, game_state, server_state):
        self._game_state = game_state
        self._server_state = server_state

    @property
    def game_state(self):
        return self._game_state

    @property
    def server_state(self):
        return self._server_state


if __name__ == "__main__":
    logging.basicConfig(level=LOGLEVEL)
    loop = asyncio.get_event_loop()
    loop.set_debug(False)

    game_st = GameData()
    server_st = ServerState(game_st)
    gserver_st = GameServerState(game_st, server_st)
    loop.create_task(main(gserver_st))
    loop.create_task(publish_game_state(gserver_st))

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        server_st.stop()

    loop.close()
