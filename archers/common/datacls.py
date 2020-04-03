import dataclasses
import time
from dataclasses import dataclass, field
from dataclasses import asdict
from typing import List, Dict, Any, Tuple
from collections import deque

@dataclass
class Event:
    _id = 0

    id: int
    ts: int
    topic: str
    params: tuple
    evt: int = 1  # event type 1=Event

    @classmethod
    def get_new_id(cls):
        cls._id += 1
        if cls._id > 5000:
            cls._id = 0
        return cls._id

@dataclass
class PlayerData:
    id: int
    ts: float
    position: List
    keys_pressed: Dict
    speed: int
    facing: int = 0  # FACE_UP...

@dataclass
class ProjectileData:
    id: int
    src_id: int
    ts: float
    position: List
    speed: int
    facing: int = 0

@dataclass
class GameData:
    players: List[PlayerData] = field(default_factory=lambda: [])
    updated_at: float = .0
    evt: int = 0  # event type 0=GameData

    def get_player_from_id(self, player_id):
        if not isinstance(player_id, int):
            raise Exception('Must be an int')
        for (i, p) in enumerate(self.players):
            if p.id == player_id:
                break
        else:
            return (None, None)
        return (i, p)

    def set_from_dict(self, indict):
        del self.players[:]
        for p in indict['players']:
            self.players.append(PlayerData(**p))
        self.updated_at = time.time()

class GameState:
    def __init__(self):
        self._last_gamedata = None
        self._gamedata = GameData()

    @property
    def gamedata(self):
        return self._gamedata

    @property
    def last_gamedata(self):
        return self._last_gamedata

    @gamedata.setter
    def gamedata(self, value):
        if self._last_gamedata is None:
            self._last_gamedata = value
        else:
            self._last_gamedata = self._gamedata
        self._gamedata = value

    def get_player_from_id(self, player_id):
        return self._gamedata.get_player_from_id(player_id)

@dataclass
class ClientPlayerData(PlayerData):
    pos_buffer: Any = field(default_factory=lambda: deque(maxlen=2))
    time_since_state_update: float = .0
    position_snapshot: List = field(default_factory=lambda: [])
    input_buffer: Any = field(default_factory=lambda: deque(maxlen=5))
    pos_corr_buff: Any = field(default_factory=lambda: deque(maxlen=2))

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if (
                k not in ['pos_buffer', 'time_since_state_update',
                'position_snapshot', 'input_buffer', 'pos_corr_buff'])}

@dataclass
class ClientProjectileData(ProjectileData):
    pos_buffer: Any = field(default_factory=lambda: deque(maxlen=2))
    time_since_state_update: float = .0
    position_snapshot: List = field(default_factory=lambda: [])
    pos_corr_buff: Any = field(default_factory=lambda: deque(maxlen=2))

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if (
                k not in ['pos_buffer', 'time_since_state_update',
                'position_snapshot', 'pos_corr_buff'])}

@dataclass
class ClientGameData(GameData):
    remote_address: str = '127.0.0.1'
    local_address_port: int = 4321
    players: List[ClientPlayerData] = field(default_factory=lambda: [])
    #projectiles: List[Tuple] = field(default_factory=lambda: [])
    projectiles: Any = field(default_factory=lambda: deque())
    # server to client
    srv_eventq: Any = field(default_factory=lambda: deque())
    # client to server
    client_eventq: Any = field(default_factory=lambda: deque())
