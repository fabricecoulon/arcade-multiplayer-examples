import math
import operator

class Vector2(object):

    __slots__ = ['x', 'y']

    def __init__(self, x, y=None):
        if isinstance(x, tuple) or isinstance(x, list):
            self.x = x[0]
            self.y = x[1]
        elif isinstance(x, Vector2):
            self.x = x.x
            self.y = x.y
        else:
            self.x = x
            self.y = y

    def __getitem__(self, i):
        if i == 0:
            return self.x
        elif i == 1:
            return self.y
        raise IndexError()

    def __iter__(self):
        yield self.x
        yield self.y

    def __len__(self):
        return 2

    def __setitem__(self, i, value):
        if i == 0:
            self.x = value
        elif i == 1:
            self.y = value
        else:
            raise IndexError()

    def __repr__(self):
        return 'Vector2(%s, %s)' % (self.x, self.y)

    def __eq__(self, other):
        if hasattr(other, "__getitem__") and len(other) == 2:
            return self.x == other[0] and self.y == other[1]
        else:
            return False

    def __ne__(self, other):
        if hasattr(other, "__getitem__") and len(other) == 2:
            return self.x != other[0] or self.y != other[1]
        else:
            return True

    def is_nonzero(self):
        return self.x != 0.0 or self.y != 0.0

    def __add__(self, other):
        if isinstance(other, Vector2):
            return Vector2(self.x + other.x, self.y + other.y)
        elif hasattr(other, "__getitem__"):
            return Vector2(self.x + other[0], self.y + other[1])
        else:
            return Vector2(self.x + other, self.y + other)
    __radd__ = __add__

    def __iadd__(self, other):
        if isinstance(other, Vector2):
            self.x += other.x
            self.y += other.y
        elif hasattr(other, "__getitem__"):
            self.x += other[0]
            self.y += other[1]
        else:
            self.x += other
            self.y += other
        return self

    def __sub__(self, other):
        if isinstance(other, Vector2):
            return Vector2(self.x - other.x, self.y - other.y)
        elif (hasattr(other, "__getitem__")):
            return Vector2(self.x - other[0], self.y - other[1])
        else:
            return Vector2(self.x - other, self.y - other)
    def __rsub__(self, other):
        if isinstance(other, Vector2):
            return Vector2(other.x - self.x, other.y - self.y)
        if (hasattr(other, "__getitem__")):
            return Vector2(other[0] - self.x, other[1] - self.y)
        else:
            return Vector2(other - self.x, other - self.y)
    def __isub__(self, other):
        if isinstance(other, Vector2):
            self.x -= other.x
            self.y -= other.y
        elif (hasattr(other, "__getitem__")):
            self.x -= other[0]
            self.y -= other[1]
        else:
            self.x -= other
            self.y -= other
        return self

    def __mul__(self, other):
        if isinstance(other, Vector2):
            return Vector2(self.x*other.x, self.y*other.y)
        if (hasattr(other, "__getitem__")):
            return Vector2(self.x*other[0], self.y*other[1])
        else:
            return Vector2(self.x*other, self.y*other)
    __rmul__ = __mul__

    def __imul__(self, other):
        if isinstance(other, Vector2):
            self.x *= other.x
            self.y *= other.y
        elif (hasattr(other, "__getitem__")):
            self.x *= other[0]
            self.y *= other[1]
        else:
            self.x *= other
            self.y *= other
        return self

    def __floordiv__(self, other):
        raise

    def __truediv__(self, other):
        # check if other is of type Vector2
        if isinstance(other, Vector2):
            return Vector2(operator.truediv(self.x, other.x),
                         operator.truediv(self.y, other.y))
        # must be a float
        return Vector2(operator.truediv(self.x, other),
                         operator.truediv(self.y, other))

    def __abs__(self):
        return Vector2(abs(self.x), abs(self.y))

    def __invert__(self):
        return Vector2(-self.x, -self.y)

    def get_length_sqrd(self):
        return self.x**2 + self.y**2

    def get_length(self):
        return math.sqrt(self.x**2 + self.y**2)

    def __setlength(self, value):
        length = self.get_length()
        self.x *= value/length
        self.y *= value/length
    length = property(get_length, __setlength)

    def rotate_rad(self, angle_radians):
        cos = math.cos(angle_radians)
        sin = math.sin(angle_radians)
        x = self.x*cos - self.y*sin
        y = self.x*sin + self.y*cos
        self.x = x
        self.y = y

    def get_rotated_rad(self, angle_radians):
        cos = math.cos(angle_radians)
        sin = math.sin(angle_radians)
        x = self.x*cos - self.y*sin
        y = self.x*sin + self.y*cos
        return Vector2(x, y)

    def rotate_deg(self, angle_degrees):
        self.rotate_rad(math.radians(angle_degrees))

    def get_rotated_deg(self, angle_degrees):
        return self.get_rotated_rad(math.radians(angle_degrees))

    def get_angle(self):
        if (self.get_length_sqrd() == 0):
            return 0
        return math.atan2(self.y, self.x)

    def __setangle(self, angle):
        self.x = self.length
        self.y = 0
        self.rotate(angle)
    angle = property(get_angle, __setangle)

    def get_angle_degrees(self):
        return math.degrees(self.get_angle())
    def __set_angle_degrees(self, angle_degrees):
        self.__setangle(math.radians(angle_degrees))
    angle_degrees = property(get_angle_degrees, __set_angle_degrees)

    def get_angle_between(self, other):
        cross = self.x*other[1] - self.y*other[0]
        dot = self.x*other[0] + self.y*other[1]
        return math.atan2(cross, dot)

    def get_angle_degrees_between(self, other):
        return math.degrees(self.get_angle_between(other))

    def get_normalized(self):
        length = self.length
        if length != 0:
            x = self.x / length
            y = self.y / length
            return Vector2(x, y)
        return Vector2(self)

    def normalize_return_length(self):
        length = self.length
        if length != 0:
            self.x /= length
            self.y /= length
        return length

    def get_perpendicular(self):
        return Vector2(-self.y, self.x)

    def get_perpendicular_normal(self):
        length = self.length
        return Vector2(-self.y/length, self.x/length)

    def dot(self, other):
        return float(self.x*other[0] + self.y*other[1])

    def get_distance(self, other):
        return math.sqrt((self.x - other[0])**2 + (self.y - other[1])**2)

    def get_dist_sqrd(self, other):
        return (self.x - other[0])**2 + (self.y - other[1])**2

    def cross(self, other):
        return self.x*other[1] - self.y*other[0]

    def get_interpolated_to(self, other, range):
        return Vector2(self.x + (other[0] - self.x)*range, self.y + (other[1] - self.y)*range)

    def get_converted_to_basis(self, x_vector, y_vector):
        x = self.dot(x_vector)/x_vector.get_length_sqrd()
        y = self.dot(y_vector)/y_vector.get_length_sqrd()
        return Vector2(x, y)

    def __get_int_xy(self):
        return int(self.x), int(self.y)
    as_int_tuple = property(__get_int_xy)

    def __get_tuple_xy(self):
        return (self.x, self.y)
    as_tuple = property(__get_tuple_xy)

    def __get_list_xy(self):
        return [self.x, self.y]
    as_list = property(__get_list_xy)



if __name__ == "__main__":
    # init w single tuple
    v1 = Vector2((0., 1.))
    # getitem
    assert (v1.x == 0. and v1.y == 1.)
    # init with 2 pos arg
    v2 = Vector2(2., 3.)
    assert (v2.x == 2. and v2.y == 3.)
    # iter
    for i, c in enumerate(v1):
        assert c == (0., 1.)[i]
    # index out of bounds exception
    try:
        print(v1[2])
    except IndexError as e:
        pass
    # len
    assert len(v1) == 2
    # set items via prop
    v1.x = 4.
    v1.y = 5.
    assert (v1.x == 4. and v1.y == 5.)
    # set_item
    v1[0] = 6.
    v1[1] = 7.
    assert (v1.x == 6. and v1.y == 7.)
    # equal
    v2.x = 6.
    v2.y = 7.
    assert (v1 == v2)
    unit = Vector2((1., 1.))
    assert (v1 != unit)
    # vector length
    assert (unit.length == math.sqrt(2))
    # rotate radians, length invariant
    unit.rotate_rad(10)
    v3 = unit.get_rotated_rad(10)
    assert math.isclose(unit.length, v3.length, abs_tol=1e-8)
    v4 = unit.get_perpendicular()
    assert (unit.get_angle_degrees_between(v4) == 90.0)
    v2.x, v2.y = (4.0, 4.0)
    assert math.isclose(v2.get_normalized().length, 1.0)
    # get new normalized vector from vector, ignore zero length
    v0 = Vector2(0,0)
    assert (v0.get_normalized() == (0., 0.))
