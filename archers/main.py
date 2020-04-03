#!/usr/bin/env python
import logging
import sys
import time
from pathlib import Path
from common.arcadegame import ArcadeGame
from common.helpers import MeasureDuration
from common.datacls import GameData, GameState, ClientGameData, PlayerData, ClientPlayerData
from common import gamethreads

WWIDTH = 800
WHEIGHT = 600

def main():
    playerid = int(sys.argv[1])   # player id should be an int
    remote_address = sys.argv[2]  # server ip address string for client to server coms
    local_address_port = int(sys.argv[3])  # listening port (int) for server to client coms
    with MeasureDuration() as m:
        time.sleep(0.001)
    print(m.get_duration_ms())
    logging.basicConfig(level=logging.ERROR)
    picsdir = Path('pics')

    gamestate = GameState()
    playerdata = PlayerData(id=playerid,ts=None,position=None,
        keys_pressed=None, speed=None)
    gamestate.gamedata.players.append(playerdata)

    cgame = ArcadeGame(WWIDTH, WHEIGHT, picsdir)
    cgame.set_update_rate(1/60)
    cgamedata = ClientGameData(remote_address=remote_address,local_address_port=local_address_port)
    cplayerdata = ClientPlayerData(id=playerid,ts=None,position=None,
        keys_pressed=None, speed=None)
    cgamedata.players.append(cplayerdata)
    cgame.setup(gamestate, cgamedata)

    cgame_thread_manager = gamethreads.GameThreadManager(gamestate, cgamedata)
    cgame.set_game_thread_manager(cgame_thread_manager)
    cgame_thread_manager.run()

    try:
        cgame.run()
    except KeyboardInterrupt:
        pass
    cgame_thread_manager.stop()

if __name__ == "__main__":
    main()
