import arcade
import sys
import time
from common.helpers import KeysPressed, MOVE_MAP, apply_movement, MeasureDuration
from common.playercharacter import PlayerCharacter
from common.projectile import Projectile
from common.vector2 import Vector2
from common.datacls import PlayerData, GameData, ClientPlayerData, ClientGameData
from common.datacls import ClientProjectileData
from collections import deque
from pubsub import pub
from common.helpers import ROOT_PLAYER_ID, TOPIC_GSUPDATE, TOPIC_NEWPLAYER
from common.helpers import FACE_RIGHT, FACE_LEFT, FACE_UP, FACE_DOWN
from common.helpers import TOPIC_PLAYERX_WEAPON_OUT, TOPIC_PLAYERX_WEAPON_SHOOT
from common.helpers import TOPIC_PLAYERX_FIRE_WEAPON
from common.helpers import PROJECTILE
from common.datacls import Event


class ArcadeGame(arcade.Window):

    def __init__(self, width, height, picsdir):
        super().__init__(width, height, title='', fullscreen=False)
        arcade.set_background_color(arcade.color.AMAZON)
        self.keys_pressed = KeysPressed()
        self.cgamedata = None
        self.picsdir = picsdir
        self.game_thread_manager = None
        self.srv_eventq = None
        self.client_eventq = None

        pub.subscribe(self.on_gamestate_update, TOPIC_GSUPDATE)
        pub.subscribe(self.on_new_player, TOPIC_NEWPLAYER)

    def setup(self, gamestate, cgamedata):
        self.gamestate = gamestate
        self.cgamedata = cgamedata
        self.all_sprites = arcade.SpriteList()
        self.players = []

        player0_sprite = PlayerCharacter(ROOT_PLAYER_ID, self.picsdir, scale=1.5)
        player0_sprite.setup()
        x = self.width // 2
        y = self.height // 2
        player0_sprite.position = [x, y]
        player0_sprite.set_check_idle_cb(lambda: not self.keys_pressed.hasKeyPressed())
        self.players.append(player0_sprite)

        self.cgamedata.players[0].ts = time.time()
        self.cgamedata.players[0].position = player0_sprite.position
        self.cgamedata.players[0].keys_pressed = self.keys_pressed.keys
        self.cgamedata.players[0].speed = player0_sprite.movement_speed

        self.all_sprites.append(player0_sprite)

        self.srv_eventq = cgamedata.srv_eventq
        self.client_eventq = cgamedata.client_eventq
        self.debug_counter = 0

    def set_game_thread_manager(self, game_thread_manager):
        self.game_thread_manager = game_thread_manager

    def interp_pos(self, player_sprite, idx):
        pos_buff = self.cgamedata.players[idx].pos_buffer

        if len(pos_buff) < 2:
            return False, None

        # These are the last two positions. p1 is the latest, p0 is the
        # one immediately preceding it.
        p0, t0 = Vector2(pos_buff[0][0]), pos_buff[0][1]
        p1, t1 = Vector2(pos_buff[1][0]), pos_buff[1][1]
        deltat = t1 - t0

        if deltat == 0:
            return False, None

        #v = (p1 - p0) / deltat
        #predicted_future_pos = v * deltat + p1
        predicted_future_pos = (2*p1 - p0)

        x = self.cgamedata.players[idx].time_since_state_update / deltat
        x = min(x, 1)
        _last_position = Vector2(player_sprite.position)
        interpolated = _last_position.get_interpolated_to(predicted_future_pos, x)
        return True, interpolated

    def update_calc_pos_client(self, dt, player_sprite, idx, interpolate=True):
        last_pos = Vector2(player_sprite.position)

        pos_corr_buff = self.cgamedata.players[idx].pos_corr_buff

        if len(pos_corr_buff) > 0:
            _new_pos = pos_corr_buff[0]
            new_pos = last_pos.get_interpolated_to(_new_pos, 0.5)
            if (_new_pos - new_pos).get_length() < 1.0:
                pos_corr_buff.popleft()
        else:
            _keys_pressed = self.keys_pressed if idx == 0 else self.cgamedata.players[idx].keys_pressed
            if _keys_pressed is None:
                return
            new_pos = apply_movement(player_sprite.movement_speed, dt, last_pos, _keys_pressed)

            diff_pos = None
            if interpolate:
                _interpolated = self.interp_pos(player_sprite, idx)
                if _interpolated[0]:
                    diff_pos = new_pos - _interpolated[1]

            if (diff_pos is not None):
                if diff_pos.get_length() > 10.0:
                    new_pos = _interpolated[1]

        player_sprite.change_x, player_sprite.change_y = new_pos - last_pos

        self.cgamedata.players[idx].time_since_state_update += dt

        if not isinstance(new_pos, list):
            _new_pos = new_pos.as_list
        else:
            _new_pos = new_pos
        self.cgamedata.players[idx].position = _new_pos
        self.cgamedata.players[idx].facing = player_sprite.state

    def on_draw(self):
        arcade.start_render()
        self.all_sprites.draw()

    def on_new_player(self, params):
        new_player_id = params[0]
        print("on_new_player new_player_id = %d" % new_player_id)
        if new_player_id == self.cgamedata.players[0].id:
            return
        _, p = self.gamestate.get_player_from_id(new_player_id)
        if p is None:
            return

        new_player_sprite = PlayerCharacter(1, self.picsdir, scale=1.5)
        new_player_sprite.setup()
        self.players.append(new_player_sprite)

        new_player = ClientPlayerData(id=new_player_id,ts=p.ts,position=p.position[:],keys_pressed=None, speed=None)
        self.cgamedata.players.append(new_player)
        new_player_sprite.position = new_player.position

        self.all_sprites.append(new_player_sprite)

    def on_gamestate_update(self, params):
        gd = params[0]
        for ps in gd.players:
            for i, pd in enumerate(self.cgamedata.players):
                if i != 0 and (ps.id == pd.id):
                    pd.pos_buffer.append((ps.position[:], time.time()))
                    pd.time_since_state_update = 0
                    pd.position_snapshot = pd.position[:]

    def process_events(self):
        if len(self.srv_eventq) > 0:
            e = self.srv_eventq.popleft()
            pub.sendMessage(e.topic, params=e.params)

    def server_to_client_pos_corr_buff(self, delta_time):
        for i, p in enumerate(self.players):
            do_corr = False
            p.set_skip_facing_change(False)
            pos_buff = self.cgamedata.players[i].pos_buffer
            if len(pos_buff) == 2:
                server_x, server_y = pos_buff[1][0]
                do_corr = True

            if i == 0 and not self.keys_pressed.hasKeyPressed():
                p.set_skip_facing_change(True)

            if do_corr:
                self.cgamedata.players[i].pos_corr_buff.append([server_x, server_y])

    def on_update(self, dt):
        self.debug_counter += 1
        if self.debug_counter > 1000:
            self.debug_counter = 0

        self.process_events()

        for idx, p in enumerate(self.players):
            self.update_calc_pos_client(dt, p, idx)

        for s in self.all_sprites:
            if isinstance(s, Projectile):
                if s.is_too_far():
                    for i, p in enumerate(self.cgamedata.projectiles):
                        if (s.id == p.src_id):
                            del self.cgamedata.projectiles[i]
                    self.all_sprites.remove(s)

        self.all_sprites.update()

        self.server_to_client_pos_corr_buff(dt)

        if not self.keys_pressed.hasKeyPressed():
            if (self.debug_counter % 100 == 0):
                for i, p in enumerate(self.players):
                        print('s #i:', i, 'pos:', self.players[i].position)

        self.all_sprites.update_animation()

    def on_fire_weapon(self, src_id):
        projectile_id = Projectile.get_new_id()
        projectile_sprite = Projectile()
        projectile_sprite.setup(projectile_id, src_id, facing=self.players[src_id].facing, position=self.players[src_id].position)
        self.all_sprites.append(projectile_sprite)

        projectile = ClientProjectileData(id=projectile_id, src_id=src_id, ts=time.time(), position=self.players[src_id].position,
                        speed=projectile_sprite.speed, facing=projectile_sprite.facing)
        _src_player_id = self.cgamedata.players[src_id].id
        projectile.src_player_id = _src_player_id
        self.cgamedata.projectiles.append(projectile)

        _event = Event(Event.get_new_id(),ts=time.time(), topic=TOPIC_PLAYERX_FIRE_WEAPON % _src_player_id,
                        params=({'src': _src_player_id, 'klass': PROJECTILE, 'obj_as_dict': projectile.to_dict()},))
        self.client_eventq.append(_event)

    def on_key_press(self, key, key_modifiers):
        if key in MOVE_MAP:
            self.keys_pressed.keys[key] = True
            _keys = self.keys_pressed.keys.copy()
            self.cgamedata.players[0].input_buffer.append(_keys)
        elif key == arcade.key.R:
            pub.sendMessage(TOPIC_PLAYERX_WEAPON_OUT % ROOT_PLAYER_ID, params=None)
        elif key == arcade.key.SPACE:
            pub.sendMessage(TOPIC_PLAYERX_WEAPON_SHOOT % ROOT_PLAYER_ID, params={'cb': self.on_fire_weapon})
        elif key == arcade.key.F:
            self.keys_pressed.reset()
            self.set_fullscreen(not self.fullscreen)
        elif key == arcade.key.X:
            print('exiting...')
            self.game_thread_manager.stop()
            time.sleep(1)
            sys.exit(0)
        elif key == arcade.key.T:
            self.players[0].set_run_mode()
            self.cgamedata.players[0].speed = self.players[0].movement_speed
            print('Run mode')
        elif key == arcade.key.Y:
            self.players[0].set_run_mode(False)
            self.cgamedata.players[0].speed = self.players[0].movement_speed
            print('Walk mode')


    def on_key_release(self, key, key_modifiers):
        if key in MOVE_MAP:
            self.keys_pressed.keys[key] = False
            _keys = self.keys_pressed.keys.copy()
            self.cgamedata.players[0].input_buffer.append(_keys)


    def run(self):
        arcade.run()
