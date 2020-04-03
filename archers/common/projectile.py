import arcade
from common.helpers import FACE_RIGHT, FACE_LEFT, FACE_UP, FACE_DOWN

PROJECTILE_SPEED = 400
MAX_DIS = 1000

class Projectile(arcade.Sprite):

    count = 0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._src_player_id = None

    def setup(self, id, src_id, scale=1.5, facing=FACE_RIGHT, position=None, max_dis=MAX_DIS):
        self.id = id
        self.src_id = src_id  # the id of the source object that created this projectile
        self.texture = arcade.load_texture('pics/arrow.png')
        self.scale = scale
        self.width = self.texture.width * self.scale
        self.height = self.texture.height * self.scale
        self.speed = PROJECTILE_SPEED
        self.facing = facing
        self.position = position
        self.max_dis = max_dis
        self.dis_x = 0
        self.dis_y = 0
        if self.facing == FACE_LEFT:
            self.turn_left(180)
        elif self.facing == FACE_UP:
            self.turn_left(90)
        elif self.facing == FACE_DOWN:
            self.turn_right(90)

    def is_too_far(self):
        if (self.dis_x > self.max_dis) or (self.dis_y > self.max_dis):
            return True
        return False

    def update_animation(self, dt):
        if self.facing == FACE_RIGHT:
            self.change_x = self.speed * dt
            self.change_y = 0
        elif self.facing == FACE_LEFT:
            self.change_x = -1 * self.speed * dt
            self.change_y = 0
        elif self.facing == FACE_UP:
            self.change_y = self.speed * dt
            self.change_x = 0
        elif self.facing == FACE_DOWN:
            self.change_y = -1 * self.speed * dt
            self.change_x = 0

        self.dis_x += abs(self.change_x)
        self.dis_y += abs(self.change_y)

    @classmethod
    def get_new_id(cls):
        cls.count += 1
        return cls.count

    @property
    def src_player_id(self):
        return self._src_player_id
    
    @src_player_id.setter
    def src_player_id(self, value):
        self._src_player_id = value
