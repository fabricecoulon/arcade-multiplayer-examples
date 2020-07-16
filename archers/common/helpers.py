import arcade
import time
from PIL import Image
from common.vector2 import Vector2
from dataclasses import dataclass, field
from typing import Dict

ROOT_PLAYER_ID = 0

FACE_RIGHT = 1
FACE_LEFT = 2
FACE_UP = 3
FACE_DOWN = 4

TOPIC_GSUPDATE = 'root.game.gamestate_update'
TOPIC_NEWPLAYER = 'root.game.new_player'
TOPIC_PLAYERX  = "root.game.player.%d"
TOPIC_PLAYERX_WEAPON_OUT = TOPIC_PLAYERX + '.weapon_out'
TOPIC_PLAYERX_WEAPON_SHOOT = TOPIC_PLAYERX + '.weapon_shoot'
TOPIC_PLAYERX_FIRE_WEAPON = TOPIC_PLAYERX + '.fire_weapon'

MOVE_MAP = {
    arcade.key.UP: Vector2(0, 1),
    arcade.key.DOWN: Vector2(0, -1),
    arcade.key.LEFT: Vector2(-1, 0),
    arcade.key.RIGHT: Vector2(1, 0),
}

# Client event to server object
PROJECTILE = 10  # 'ProjectileData'

@dataclass
class KeysPressed:
    keys: Dict = field(default_factory=lambda: {k: False for k in MOVE_MAP})

    def reset(self):
        for k in MOVE_MAP:
            self.keys[k] = False

    def hasKeyPressed(self):
        return any(self.keys.values())


def apply_movement(speed, dt, current_position, kp, normalize=True):
    if isinstance(kp, dict):
        _v = sum(kp[k] * MOVE_MAP[k] for k in kp)
    else:
        _v = sum(kp.keys[k] * MOVE_MAP[k] for k in kp.keys)
    if normalize:
        _delta_position = _v.get_normalized()
    else:
        _delta_position = _v
    res = current_position + (_delta_position * speed * dt)
    return res


def getSpriteFromSpriteSheet(filename, width=None, height=None, rows=None, cols=None, rects=None):
    argsType = '' # there should be exactly 1 set of arguments passed (i.e. don't pass width/height AND rows/cols)
    if (width is not None or height is not None) and (argsType == ''):
        argsType = 'width/height'
        assert width is not None and height is not None, 'Both width and height must be specified'
        assert type(width) == int and width > 0, 'width arg must be a non-zero positive integer'
        assert type(height) == int and height > 0, 'height arg must be a non-zero positive integer'
    if (rows is not None or cols is not None) and (argsType == ''):
        argsType = 'rows/cols'
        assert rows is not None and cols is not None, 'Both rows and cols must be specified'
        assert type(rows) == int and rows > 0, 'rows arg must be a non-zero positive integer'
        assert type(cols) == int and cols > 0, 'cols arg must be a non-zero positive integer'
    if (rects is not None) and (argsType == ''):
        argsType = 'rects'
        for i, rect in enumerate(rects):
            assert len(rect) == 4, 'rect at index %s is not a sequence of four ints: (left, top, width, height)' % (i)
            assert (type(rect[0]), type(rect[1]), type(rect[2]), type(rect[3])) == (int, int, int, int), 'rect '
    if (rects is None):
        rects = []

    if argsType == '':
        raise ValueError('Only pass one set of args: width & height, rows & cols, *or* rects')

    sheetImage = Image.open(filename)
    print("sheetImage.size: {}".format(sheetImage.size))
    sheetImage.close()

    if argsType == 'width/height':
        for y in range(0, sheetImage.height, height):
            if y + height > sheetImage.height:
                continue
            for x in range(0, sheetImage.width, width):
                if x + width > sheetImage.width:
                    continue
                rects.append((x, y, width, height))

    if argsType == 'rows/cols':
        spriteWidth = sheetImage.width // cols
        spriteHeight = sheetImage.height // rows

        for y in range(0, sheetImage.height, spriteHeight):
            if y + spriteHeight > sheetImage.height:
                continue
            for x in range(0, sheetImage.width, spriteWidth):
                if x + spriteWidth > sheetImage.width:
                    continue

                rects.append([x, y, spriteWidth, spriteHeight])

    print("#sprites: {}".format(len(rects)))
    # create a list of textures objects from the sprite sheet
    textures = arcade.load_textures(filename, rects)
    return textures


class MeasureDuration:
    def __init__(self):
        self.start = None
        self.end = None
        self.duration = 0

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end = time.time()
        self.duration = self.end - self.start

    def get_duration_ms(self):
        return self.duration * 1000
