import arcade
from common.helpers import getSpriteFromSpriteSheet
from common.vector2 import Vector2
from common.helpers import FACE_RIGHT, FACE_LEFT, FACE_UP, FACE_DOWN
from pubsub import pub
from common.helpers import TOPIC_PLAYERX_WEAPON_OUT, TOPIC_PLAYERX_WEAPON_SHOOT

RUN_SPEED = 150
WALK_SPEED = 100
MOVEMENT_SPEED = WALK_SPEED


class PlayerCharacter(arcade.Sprite):

    def __init__(self, id, picsdir, **kwargs):
        self.picsdir = picsdir
        super().__init__(**kwargs)
        self.state = FACE_RIGHT
        self.stand_right_textures = []
        self.stand_left_textures = []
        self.walk_left_textures = []
        self.walk_right_textures = []
        self.walk_up_textures = []
        self.walk_down_textures = []
        self.cur_texture_index = 0
        self.movement_speed = MOVEMENT_SPEED
        self.texture_change_distance = 10
        self.last_texture_change_center_x = 0
        self.last_texture_change_center_y = 0
        self.texture_change_frames = 3
        self.frame = 0
        self.weapon_out = False
        self.weapon_out_anim = False
        self.weapon_out_anim_cb = None
        self.weapon_in_anim = False
        self.fire_weapon = False
        self.fire_weapon_anim = False
        self.fire_weapon_anim_cb = None
        self.cb_params = None
        self.cur_take_bow_texture_index = 0
        self.stand_up_take_bow_textures = []
        self.stand_left_take_bow_textures = []
        self.stand_down_take_bow_textures = []
        self.stand_right_take_bow_textures = []
        self.stand_textures = None
        self.walk_textures = None
        self.take_bow_textures = None
        self.fire_bow_textures = None
        self.stand_up_fire_bow_textures = []
        self.stand_left_fire_bow_textures = []
        self.stand_down_fire_bow_textures = []
        self.stand_right_fire_bow_textures = []
        self.cur_fire_bow_texture_index = 0

        self.is_idle_cb = lambda: False
        self.skip_facing_change = False
        self._id = id

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, value):
        if (value < 0):
            raise Exception("Only unsigned int allowed")
        self._id = value

    @property
    def facing(self):
        return self.state

    def set_run_mode(self, run=True):
        if run:
            self.movement_speed = RUN_SPEED
            self.texture_change_distance = 8
        else:
            self.movement_speed = WALK_SPEED
            self.texture_change_distance = 10

    def set_check_idle_cb(self, func):
        self.is_idle_cb = func

    def set_skip_facing_change(self, val):
        self.skip_facing_change = val

    def setup(self):
        pub.subscribe(self.on_weapon_out, TOPIC_PLAYERX_WEAPON_OUT % self.id)
        pub.subscribe(self.on_weapon_shoot, TOPIC_PLAYERX_WEAPON_SHOOT % self.id)

        self.player_textures = getSpriteFromSpriteSheet(self.picsdir / 'playercharacter.png', width=64, height=64)
        # stand right = 15
        self.stand_right_textures.extend([self.player_textures[15]])
        # stand left = 5
        self.stand_left_textures.extend([self.player_textures[5]])
        # walk up index = 60..64 (walk_up_textures)
        self.walk_up_textures.extend(self.player_textures[60:65])
        # walk left 65..69 (walk_left_textures)
        self.walk_left_textures.extend(self.player_textures[65:70])
        # walk down 70..74 (walk_down_textures)
        self.walk_down_textures.extend(self.player_textures[70:75])
        # walk right 75..79 (walk_right_textures)
        self.walk_right_textures.extend(self.player_textures[75:80])

        # stand up take bow
        self.stand_up_take_bow_textures.extend(self.player_textures[120:125])
        self.stand_left_take_bow_textures.extend(self.player_textures[125:130])
        self.stand_down_take_bow_textures.extend(self.player_textures[130:135])
        self.stand_right_take_bow_textures.extend(self.player_textures[135:140])

        # stand up fire bow
        self.stand_up_fire_bow_textures.extend(self.player_textures[140:145])
        self.stand_left_fire_bow_textures.extend(self.player_textures[145:150])
        self.stand_down_fire_bow_textures.extend(self.player_textures[150:155])
        self.stand_right_fire_bow_textures.extend(self.player_textures[155:160])

        self.stand_textures = {
            FACE_LEFT: self.stand_left_textures[0],
            FACE_RIGHT: self.stand_right_textures[0],
            FACE_UP: self.walk_up_textures[0],
            FACE_DOWN: self.walk_down_textures[0]
        }
        self.walk_textures = {
            FACE_LEFT: self.walk_left_textures,
            FACE_RIGHT: self.walk_right_textures,
            FACE_UP: self.walk_up_textures,
            FACE_DOWN: self.walk_down_textures
        }
        self.take_bow_textures = {
            FACE_LEFT: self.stand_left_take_bow_textures,
            FACE_RIGHT: self.stand_right_take_bow_textures,
            FACE_UP: self.stand_up_take_bow_textures,
            FACE_DOWN: self.stand_down_take_bow_textures
        }
        self.fire_bow_textures = {
            FACE_LEFT: self.stand_left_fire_bow_textures,
            FACE_RIGHT: self.stand_right_fire_bow_textures,
            FACE_UP: self.stand_up_fire_bow_textures,
            FACE_DOWN: self.stand_down_fire_bow_textures
        }

    def on_weapon_out(self, params):
        self.cb_params = params
        if not self.weapon_out:
            self.weapon_out_anim = True
        else:
            self.weapon_in_anim = True

    def on_weapon_shoot(self, params):
        self.cb_params = params
        if not self.weapon_out:
            self.weapon_out_anim = True
            self.weapon_out_anim_cb = self.on_weapon_shoot
        else:
            self.fire_weapon_anim = True
            self.fire_weapon_cb = self.cb_params['cb']

    def _get_take_bow_out_or_in_texture(self):
        _texture_list = self.take_bow_textures[self.state]
        if self.weapon_out_anim:
            _texture = _texture_list[self.cur_take_bow_texture_index]
            self.cur_take_bow_texture_index += 1
            if self.cur_take_bow_texture_index >= len(_texture_list):
                self.cur_take_bow_texture_index = 0
                self.weapon_out_anim = False
                self.frame = 0
                self.weapon_out = True
                if self.weapon_out_anim_cb:
                    self.weapon_out_anim_cb(self.cb_params)
                    self.weapon_out_anim_cb = None
        elif self.weapon_in_anim:
            if self.cur_take_bow_texture_index == 0:
                self.cur_take_bow_texture_index = len(_texture_list) - 1
            _texture = _texture_list[self.cur_take_bow_texture_index]
            self.cur_take_bow_texture_index -= 1
            if self.cur_take_bow_texture_index == 0:
                self.weapon_in_anim = False
                self.frame = 0
                self.weapon_out = False
        else:
            raise RuntimeError('Not implemented')
        return _texture

    def _get_fire_bow_texture(self):
        _texture_list = self.fire_bow_textures[self.state]
        _texture = _texture_list[self.cur_fire_bow_texture_index]
        self.cur_fire_bow_texture_index += 1
        if self.cur_fire_bow_texture_index >= len(_texture_list):
            self.cur_fire_bow_texture_index = 0
            self.fire_weapon_anim = False
            self.frame = 0
            if self.fire_weapon_cb:
                self.fire_weapon_cb(self.id)
                self.fire_weapon_cb = None
        return _texture

    def update_idle_animation(self, delta_time):
        _texture = None

        if self.weapon_out_anim or self.weapon_in_anim:
            if (self.frame % self.texture_change_frames) == 0:
                _texture = self._get_take_bow_out_or_in_texture()
            self.frame += 1
        elif self.weapon_out and self.fire_weapon_anim:
            if (self.frame % self.texture_change_frames) == 0:
                _texture = self._get_fire_bow_texture()
            self.frame += 1
        elif not self.weapon_out:
            _texture = self.stand_textures[self.state]

        return _texture

    def update_animation(self, delta_time):
        _distance = (Vector2(self.last_texture_change_center_x, self.last_texture_change_center_y) -
            Vector2(self.center_x, self.center_y)).get_length()
        _texture_list = []
        _curr_texture = None
        _change_direction = False

        if self.change_x > 0 and self.change_y == 0 and self.state != FACE_RIGHT \
                and len(self.walk_right_textures) > 0:
            self.state = FACE_RIGHT
            _change_direction = True
        elif self.change_x < 0 and self.change_y == 0 and self.state != FACE_LEFT \
                and len(self.walk_left_textures) > 0:
            self.state = FACE_LEFT
            _change_direction = True
        elif self.change_y < 0 and self.change_x == 0 and self.state != FACE_DOWN \
                and len(self.walk_down_textures) > 0:
            self.state = FACE_DOWN
            _change_direction = True
        elif self.change_y > 0 and self.change_x == 0 and self.state != FACE_UP \
                and len(self.walk_up_textures) > 0:
            self.state = FACE_UP
            _change_direction = True

        if ((not self.skip_facing_change) and _change_direction) or \
            (_distance >= self.texture_change_distance):
            self.weapon_out = False
            self.last_texture_change_center_x = self.center_x
            self.last_texture_change_center_y = self.center_y
            texture_list = self.walk_textures[self.state]
            self.cur_texture_index += 1
            if self.cur_texture_index >= len(texture_list):
                self.cur_texture_index = 0
            _curr_texture = texture_list[self.cur_texture_index]
        elif (not _change_direction and (self.change_x == 0 and self.change_y == 0)) \
                or self.is_idle_cb():
            _curr_texture = self.update_idle_animation(delta_time)

        if _curr_texture:
            self.texture = _curr_texture

        if self.texture is None:
            raise RuntimeError("Error, no texture set")
        else:
            self.width = self.texture.width * self.scale
            self.height = self.texture.height * self.scale
