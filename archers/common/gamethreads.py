import threading
import asyncio
import logging
import time
from copy import copy
from dataclasses import asdict
from common.helpers import MeasureDuration
from common.datacls import Event, GameData, GameState
from common.protocol import EndpointHelper, RPCProtocol
from common.helpers import TOPIC_GSUPDATE, TOPIC_NEWPLAYER

UPS_PLAYER = 30  # updates per second
UPS_PLAYER_60 = 60
#UPS_PLAYER = 5
UPS_PLAYER_SLEEPT = 1/UPS_PLAYER
UPS_PLAYER_SLEEPT_60 = 1/UPS_PLAYER_60
UPS_PLAYER_SLEEPT_30 = 1/30
UPS_GAME = 2
UPS_GAME_SLEEPT = 1/UPS_GAME

class RPCServer2ClientProtocol(RPCProtocol):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._counter = 0
        self.gamestate = None
        self.cgamedata = None

    def setup(self, gamestate, cgamedata):
        if not isinstance(gamestate, GameState):
            raise Exception("not a GameState")
        if not isinstance(cgamedata, GameData):
            raise Exception("not a GameData")

    def rpc_ff_listen_for_game_state_or_event(self, sender, state_or_event):
        if self.cgamedata and state_or_event['evt'] == 1:
            self.cgamedata.srv_eventq.append(Event(**state_or_event))
        elif self.gamedata and state_or_event['evt'] == 0:
            self.gamestate.gamedata = GameData()
            self.gamestate.gamedata.set_from_dict(state_or_event)
            self.cgamedata.srv_eventq.append(Event(Event.get_new_id(), time.time(), TOPIC_GSUPDATE, (self.gamestate.gamedata,)))

        self._counter += 1
        if (self._counter >= 1000):
            self._counter = 0


class GameThreadManager:
    def __init__(self, gamestate=None, cgamedata=None):
        self._loop = asyncio.new_event_loop()
        self._loop.set_debug(False)
        asyncio.set_event_loop(self._loop)
        self._running = False
        self.remote_address = (cgamedata.remote_address, 1234)  # For client to server coms
        self.local_address = ('0.0.0.0', cgamedata.local_address_port) # For server to client coms
        self.endpoint_helper = EndpointHelper(RPCProtocol, None)
        self.logger = logging.getLogger(__name__)
        self.protocol = None # client to server proto
        self.protocol2 = None # server to client proto
        self.remote_ep = None
        self.local_ep = None
        self._counter = 0
        self._gamestate = gamestate
        self._cgamedata = cgamedata
        self._thread = None

    def run(self):
        if not self._thread:
            self._thread = threading.Thread(target=self._main_loop_worker, args=(self._gamestate,self._cgamedata,), daemon=True)
        self._thread.start()

    def stop(self):
        self.logger.debug('Stopping...')
        self._loop.create_task(self.remove_player(self._gamestate, self._cgamedata))
        self._loop.stop()
        if self._thread:
            self._thread.join()
        self.logger.debug('Stopped')

    def _main_loop_worker(self, gamestate, cgamedata):
        self._running = True
        self.logger.debug("_main_loop_worker started")
        self._loop.create_task(self.set_player_state(gamestate, cgamedata))
        self._loop.create_task(self.get_player_state(gamestate, cgamedata))
        self._loop.create_task(self.listen_for_game_state(gamestate, cgamedata))

        self._loop.create_task(self.check_client2server_events(gamestate, cgamedata))

        self._loop.run_forever()

    async def init_player_state(self, gamestate, cgamedata):
        result = await self.protocol.create_player(self.remote_address, cgamedata.players[0].id, cgamedata.local_address_port)
        if result[0]:
            cgamedata.players[0].id = result[1]['id']
        else:
            print("init_player_state: create_player failed")
            return False
 
        result = await self.protocol.get_game_state(self.remote_address)
        if result[0]:
            gamestate.gamedata = GameData()
            gamestate.gamedata.set_from_dict(result[1])
        else:
            print("init_player_state: get_game_state failed")
            return False

        if len(cgamedata.players) < len(gamestate.gamedata.players):
            for p in gamestate.gamedata.players:
                if p.id != cgamedata.players[0].id:
                    print("creating fake event for player %d" % p.id)
                    cgamedata.srv_eventq.append(Event(Event.get_new_id(), time.time(), TOPIC_NEWPLAYER, (p.id,)))
                    break

        return True

    async def remove_player(self, gamestate, cgamedata):
        res = await self.protocol.delete_player(self.remote_address, cgamedata.players[0].id)
        return res

    async def set_player_state(self, gamestate, cgamedata):
        self.logger.info("set_player_state started (%s)" % str(self.remote_address))
        self.remote_ep, self.protocol = await self.endpoint_helper.open_remote_endpoint(*self.remote_address)
        _ = await self.init_player_state(gamestate, cgamedata)
        while (self._running):
            self._counter += 1
            if (self._counter >= 1000):
                self._counter = 0
            if (len(cgamedata.players) > 0) and (len(cgamedata.players[0].input_buffer) > 0):
                _keys = cgamedata.players[0].input_buffer.popleft()
                cgamedata.players[0].keys_pressed = _keys
                cgamedata.players[0].ts = time.time()
                _cplayer_state = cgamedata.players[0].to_dict()
                self.protocol.ff_set_player_state(self.remote_address, _cplayer_state)
            await asyncio.sleep(UPS_PLAYER_SLEEPT_60)

    async def listen_for_game_state(self, gamestate, cgamedata):
        self.logger.debug("get_game_state started")
        endpoint_helper = EndpointHelper(RPCServer2ClientProtocol, None)
        self.local_ep, self.protocol2 = await endpoint_helper.open_local_endpoint(*self.local_address)
        self.protocol2.cgamedata = cgamedata
        self.protocol2.gamestate = gamestate
        while self._running:
            await asyncio.sleep(1)

    async def get_player_state(self, gamestate, cgamedata):
        self.logger.debug("get_player_state started")
        while self._running:
            if not self.protocol:
                await asyncio.sleep(0.1)
                continue

            result = await self.protocol.get_player_state(self.remote_address, cgamedata.players[0].id)
            if (len(cgamedata.players) > 0) and result[0]:
                if result[1] is not None:
                    pos = result[1][:]
                    cgamedata.players[0].pos_buffer.append((pos, time.time()))
                    cgamedata.players[0].time_since_state_update = 0
                    cgamedata.players[0].position_snapshot = cgamedata.players[0].position[:]
            elif not result[0]:
                self.logger.debug('get_player_state: False from server')

            await asyncio.sleep(UPS_PLAYER_SLEEPT_30)

    async def check_client2server_events(self, gamestate, cgamedata):
        self.logger.debug("check_client2server_events started")
        while self._running:
            while len(cgamedata.client_eventq) > 0:
                evt = cgamedata.client_eventq.popleft()
                self.protocol.ff_process_client_events(self.remote_address, asdict(evt))
            await asyncio.sleep(UPS_PLAYER_SLEEPT_60)
