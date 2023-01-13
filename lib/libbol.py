import json
from struct import unpack, pack
from numpy import ndarray, array
from math import cos, sin
from .vectors import Vector3
from collections import OrderedDict
from io import BytesIO
from copy import deepcopy
from scipy.spatial.transform import Rotation as R

import numpy

def read_uint8(f):
    return unpack(">B", f.read(1))[0]

def read_int8(f):
    return unpack(">b", f.read(1))[0]

def read_int16(f):
    return unpack(">h", f.read(2))[0]


def read_uint16(f):
    return unpack(">H", f.read(2))[0]


def read_uint24(f):
    return unpack(">I", b"\x00"+f.read(3))[0]


def read_uint32(f):
    return unpack(">I", f.read(4))[0]


def read_float(f):
    return unpack(">f", f.read(4))[0]


def read_string(f):
    start = f.tell()

    next = f.read(1)
    n = 0

    if next != b"\x00":
        next = f.read(1)
        n += 1
    if n > 0:
        curr = f.tell()
        f.seek(start)
        string = f.read(n)
        f.seek(curr)
    else:
        string = ""

    return string


def write_uint16(f, val):
    f.write(pack(">H", val))


PADDING = b"This is padding data to align"


def write_padding(f, multiple):
    next_aligned = (f.tell() + (multiple - 1)) & ~(multiple - 1)

    diff = next_aligned - f.tell()

    for i in range(diff):
        pos = i % len(PADDING)
        f.write(PADDING[pos:pos + 1])


class Rotation(object):
    def __init__(self, forward, up, left):
        self.mtx = ndarray(shape=(4,4), dtype=float, order="F")

        self.mtx[0][0] = forward.x
        self.mtx[0][1] = -forward.z
        self.mtx[0][2] = forward.y
        self.mtx[0][3] = 0.0

        self.mtx[1][0] = left.x
        self.mtx[1][1] = -left.z
        self.mtx[1][2] = left.y
        self.mtx[1][3] = 0.0

        self.mtx[2][0] = up.x
        self.mtx[2][1] = -up.z
        self.mtx[2][2] = up.y
        self.mtx[2][3] = 0.0

        self.mtx[3][0] = self.mtx[3][1] = self.mtx[3][2] = 0.0
        self.mtx[3][3] = 1.0

    @classmethod
    def from_matrix(cls, matrix):
        rot = Rotation.default()
        rot.mtx = ndarray(shape=(4,4), dtype=float, order="F")
        rot.mtx[0][0:3] = matrix[0]
        rot.mtx[1][0:3] = matrix[1]
        rot.mtx[2][0:3] = matrix[2]
        rot.mtx[3][0] = rot.mtx[3][1] = rot.mtx[3][2] = 0.0
        rot.mtx[3][3] = 1.0


        return rot

    def rotate_around_x(self, degrees):
        mtx = ndarray(shape=(4,4), dtype=float, order="F", buffer=array([
            cos(degrees), 0.0, -sin(degrees), 0.0,
            0.0, 1.0, 0.0, 0.0,
            sin(degrees), 0.0, cos(degrees), 0.0,
            0.0, 0.0, 0.0, 1.0
        ]))

        self.mtx = self.mtx.dot(mtx)

    def rotate_around_y(self, degrees):
        mtx = ndarray(shape=(4,4), dtype=float, order="F", buffer=array([
            1.0, 0.0, 0.0, 0.0,
            0.0, cos(degrees), -sin(degrees), 0.0,
            0.0, sin(degrees), cos(degrees), 0.0,
            0.0, 0.0, 0.0, 1.0
        ]))

        self.mtx = self.mtx.dot(mtx)

    def rotate_around_z(self, degrees):
        mtx = ndarray(shape=(4,4), dtype=float, order="F", buffer=array([
            cos(degrees),-sin(degrees), 0.0, 0.0,
            sin(degrees), cos(degrees), 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0
        ]))

        self.mtx = self.mtx.dot(mtx)

    @classmethod
    def default(cls):
        return cls(Vector3(1, 0, 0),
                   Vector3(0, 1, 0),
                   Vector3(0, 0, -1))

    @classmethod
    def from_mkdd_rotation(cls,
                           s16forwardx, s16forwardy, s16forwardz,
                           s16upx, s16upy, s16upz):
        forward = Vector3(s16forwardx * 0.0001, s16forwardy * 0.0001, s16forwardz * 0.0001)
        up = Vector3(s16upx * 0.0001, s16upy * 0.0001, s16upz * 0.0001)
        left = up.cross(forward)

        return cls(forward, up, left)

    @classmethod
    def from_file(cls, f):
        return cls.from_mkdd_rotation(
            read_int16(f), read_int16(f), read_int16(f),
            read_int16(f), read_int16(f), read_int16(f)
        )

    def get_vectors(self):
        forward = Vector3(self.mtx[0][0], self.mtx[0][2], -self.mtx[0][1])
        up = Vector3(self.mtx[2][0], self.mtx[2][2], -self.mtx[2][1])
        left = Vector3(self.mtx[1][0], self.mtx[1][2], -self.mtx[1][1])
        return forward, up, left

    def set_vectors(self, forward, up, left):
        self.mtx[0][0] = forward.x
        self.mtx[0][1] = -forward.z
        self.mtx[0][2] = forward.y
        self.mtx[0][3] = 0.0

        self.mtx[1][0] = left.x
        self.mtx[1][1] = -left.z
        self.mtx[1][2] = left.y
        self.mtx[1][3] = 0.0

        self.mtx[2][0] = up.x
        self.mtx[2][1] = -up.z
        self.mtx[2][2] = up.y
        self.mtx[2][3] = 0.0

        self.mtx[3][0] = self.mtx[3][1] = self.mtx[3][2] = 0.0
        self.mtx[3][3] = 1.0

    def write(self, f):
        forward = Vector3(self.mtx[0][0], self.mtx[0][2], -self.mtx[0][1])
        up = Vector3(self.mtx[2][0], self.mtx[2][2], -self.mtx[2][1])

        f.write(pack(">hhh",
                     int(round(forward.x * 10000)),
                     int(round(forward.y * 10000)),
                     int(round(forward.z * 10000))
                     ))
        f.write(pack(">hhh",
                     int(round(up.x * 10000)),
                     int(round(up.y * 10000)),
                     int(round(up.z * 10000))
                     ))

    def get_euler(self):
        rot_matrix = [
                        [ self.mtx[0][0], self.mtx[1][0], self.mtx[2][0] ],
                        [ self.mtx[0][1], self.mtx[1][1], self.mtx[2][1] ],
                        [ self.mtx[0][2], self.mtx[1][2], self.mtx[2][2] ]

                        ]
        #print(rot_matrix)
        r = R.from_matrix( rot_matrix )
        #r = R.from_rotvec( [[self.mtx[0][0], self.mtx[0][2]  , -self.mtx[0][1]] ] )
        vec =  [int(x) for x in r.as_euler('xyz', degrees = True)]
        #print(vec)
        vec[1], vec[2] = vec[2], -1 * vec[1]
        vec[1] = vec[1] + 90
        #print(vec)


        return vec



    @classmethod
    def from_euler(cls, degs):
        degs.y = degs.y - 90
        degs.y, degs.z = degs.z * -1, degs.y

        r = R.from_euler('xyz', [degs.x, degs.y, degs.z], degrees=True)
        vecs = r.as_matrix()
        vecs = vecs.transpose()


        return Rotation.from_matrix(vecs)


    def copy(self):
        return deepcopy(self)

class ObjectContainer(list):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.assoc = None

    @classmethod
    def from_empty(cls):
        container = cls()
        return container

    @classmethod
    def from_file(cls, f, count, objcls):
        container = cls()


        for i in range(count):
            obj = objcls.from_file(f)
            container.append(obj)

        return container




ENEMYITEMPOINT = 1
CHECKPOINT = 2
ROUTEGROUP = 3
ROUTEPOINT = 4
OBJECTS = 5
KARTPOINT = 6
AREA = 7
CAMERA = 8
RESPAWNPOINT = 9
LIGHTPARAM = 10
MINIGAME = 11


class ColorRGB(object):
    def __init__(self, r, g, b):
        self.r = r
        self.g = g
        self.b = b

    @classmethod
    def from_file(cls, f):
        return cls(read_uint8(f), read_uint8(f), read_uint8(f))

    def write(self, f):
        f.write(pack(">BBB", self.r, self.g, self.b))

class ColorRGBA(ColorRGB):
    def __init__(self, r, g, b, a):
        super().__init__(r, g, b)
        self.a = a

    @classmethod
    def from_file(cls, f):
        return cls(*unpack(">BBBB", f.read(4)))

    def write(self, f):
        super().write(f)
        f.write(pack(">B", self.a))


# Section 1
# Enemy/Item Route Code Start
class EnemyPoint(object):
    def __init__(self,
                 position,
                 driftdirection,
                 link,
                 scale,
                 swerve,
                 itemsonly,
                 group,
                 driftacuteness,
                 driftduration,
                 driftsupplement,
                 nomushroomzone):
        self.position = position
        self.driftdirection = driftdirection
        self.link = link
        self.scale = scale
        self.swerve = swerve
        self.itemsonly = itemsonly
        self.group = group
        self.driftacuteness = driftacuteness
        self.driftduration = driftduration
        self.driftsupplement = driftsupplement
        self.nomushroomzone = nomushroomzone

        assert self.swerve in (-3, -2, -1, 0, 1, 2, 3)
        assert self.itemsonly in (0, 1)
        assert self.driftdirection in (0, 1, 2)
        assert 0 <= self.driftacuteness <= 180
        assert self.nomushroomzone in (0, 1)

    @classmethod
    def new(cls):
        return cls(
            Vector3(0.0, 0.0, 0.0),
            0, -1, 1000.0, 0, 0, 0, 0, 0, 0, 0
        )


    @classmethod
    def from_file(cls, f, old_bol=False):
        start = f.tell()
        args = [Vector3(*unpack(">fff", f.read(12)))]
        if not old_bol:
            args.extend(unpack(">HhfbBBBBBB", f.read(15)))
            padding = f.read(5)  # padding
            #assert padding == b"\x00" * 5
        else:
            args.extend(unpack(">HhfHBB", f.read(12)))
            args.extend((0, 0))

        obj = cls(*args)
        obj._size = f.tell() - start
        if old_bol:
            obj._size += 8
        return obj

    def copy(self):
        point = self.__class__.new()
        point.position = self.position.copy()
        point.driftdirection = self.driftdirection
        point.link = self.link
        point.scale = self.scale
        point.swerve = self.swerve
        point.itemsonly = self.itemsonly
        point.group = self.group
        point.driftacuteness = self.driftacuteness
        point.driftduration = self.driftduration
        point.driftsupplement = self.driftsupplement
        point.nomushroomzone = self.nomushroomzone

        return point


    def write(self, f):

        start = f.tell()
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        f.write(pack(">Hhf", self.driftdirection, self.link, self.scale))
        f.write(pack(">bBBBBBB", self.swerve, self.itemsonly, self.group, self.driftacuteness, self.driftduration, self.driftsupplement, self.nomushroomzone))
        f.write(b"\x01"*5)
        #assert f.tell() - start == self._size

class EnemyPointGroup(object):
    def __init__(self):
        self.points = []
        self.id = 0
        self.prev = []
        self.next = []

    @classmethod
    def new(cls):
        return cls()

    def insert_point(self, enemypoint, index=-1):
        self.points.insert(index, enemypoint)

    def move_point(self, index, targetindex):
        point = self.points.pop(index)
        self.points.insert(targetindex, point)

    def copy_group(self, new_id):
        group = EnemyPointGroup()
        group.id = new_id
        for point in self.points:
            new_point = point.copy()
            new_point.group = new_id
            group.points.append(new_point)

        return group

    def copy_group_after(self, new_id, point):
        group = EnemyPointGroup()
        group.id = new_id
        pos = self.points.index(point)

        # Check if the element is the last element
        if not len(self.points)-1 == pos:
            for point in self.points[pos+1:]:
                new_point = point.copy()
                new_point.group = new_id
                group.points.append(new_point)

        return group

    def remove_after(self, point):
        pos = self.points.index(point)
        self.points = self.points[:pos+1]

class EnemyPointGroups(object):
    def __init__(self):
        self.groups = []

    @classmethod
    def from_file(cls, f, count, old_bol=False):
        enemypointgroups = cls()
        group_ids = {}
        curr_group = None

        for i in range(count):
            enemypoint = EnemyPoint.from_file(f, old_bol)
            #print("Point", i, "in group", enemypoint.group, "links to", enemypoint.link)
            if enemypoint.group not in group_ids:
                # start of group
                curr_group = EnemyPointGroup()
                curr_group.id = enemypoint.group
                group_ids[enemypoint.group] = curr_group
                curr_group.points.append(enemypoint)
                enemypointgroups.groups.append(curr_group)
            else:
                group_ids[enemypoint.group].points.append(enemypoint)

        return enemypointgroups



    def points(self):
        for group in self.groups:
            for point in group.points:
                yield point

    def new_group_id(self):
        return len(self.groups)

    def used_links(self):
        links = []
        for group in self.groups:
            for point in group.points:
                point: EnemyPoint
                if point.link != -1:
                    if point.link not in links:
                        links.append(point.link)

        return links

    def new_link_id(self):
        existing_links = self.used_links()
        existing_links.sort()
        if len(existing_links) == 0:
            return 0

        max_link = existing_links[-1]

        for i in range(max_link):
            if i not in existing_links:
                return i

        return max_link+1
    def assign_prev_next(self):
        linked_points = [ [[], []] for x in range(0, len(self.groups) ) ]

        for idx, group in enumerate( self.groups ):
            start_point = group.points[0]
            end_point = group.points[-1]

            if start_point.link == -1 or end_point.link == -1:
                raise Exception ("Enemy groups are not fully linked correctly")


            linked_points[start_point.link][1].append(idx)
            #print("group " + str(idx) + " is a prev in link " + str(start_point.link)  )
            linked_points[end_point.link][0].append(idx)
            #print("group " + str(idx) + " is a next in link " + str(end_point.link)  )


        for idx, links in enumerate(linked_points):
            #print(links)
            #links is a list with [0] being the previous groups and [1] being the next groups
            for ix, group in enumerate(links[0]):
                next_arr = links[1].copy()
                while len(next_arr) < 6:
                    next_arr.append(-1)
                self.groups[group].next = next_arr
                #print("group " + str(group) + " has a next array of " + str(next_arr) )

            for ix, group in enumerate(links[1]):
                prev_arr = links[0].copy()
                while len(prev_arr) < 6:
                    prev_arr.append(-1)
                self.groups[group].prev = prev_arr
                #print("group " + str(group) + " has a prev array of " + str(prev_arr) )


# Enemy/Item Route Code End
##########
# Section 2
# Checkpoint Group Code Start
class CheckpointGroup(object):
    def __init__(self, grouplink):
        self.points = []
        self._pointcount = 0
        self.grouplink = grouplink
        self.prevgroup = [0, -1, -1, -1, -1, -1]
        self.nextgroup = [0, -1, -1, -1, -1, -1]

    @classmethod
    def new(cls):
        return cls(0)

    def copy_group(self, new_id):
        group = CheckpointGroup(new_id)
        group.grouplink = new_id
        group.prevgroup = deepcopy(self.prevgroup)
        group.nextgroup = deepcopy(self.nextgroup)

        for point in self.points:
            new_point = deepcopy(point)
            group.points.append(new_point)

        return group

    def copy_group_after(self, new_id, point):
        group = CheckpointGroup(new_id)
        pos = self.points.index(point)

        # Check if the element is the last element
        if not len(self.points)-1 == pos:
            for point in self.points[pos+1:]:
                new_point = deepcopy(point)
                group.points.append(new_point)

        return group

    def remove_after(self, point):
        pos = self.points.index(point)
        self.points = self.points[:pos+1]

    @classmethod
    def from_file(cls, f):
        pointcount = read_uint16(f)
        checkpointgroup = cls(read_uint16(f))
        checkpointgroup._pointcount = pointcount

        for i in range(4):
            checkpointgroup.prevgroup[i] = read_int16(f)

        for i in range(4):
            checkpointgroup.nextgroup[i] = read_int16(f)

        return checkpointgroup





    def write(self, f):
        self._pointcount = len(self.points)

        f.write(pack(">HH", self._pointcount, self.grouplink))
        f.write(pack(">hhhh", *self.prevgroup[0:4]))
        f.write(pack(">hhhh", *self.nextgroup[0:4]))

class Checkpoint(object):
    def __init__(self, start, end, unk1=0, unk2=0, unk3=0, unk4=0):
        self.start = start
        self.end = end
        self.mid = (start+end)/2.0
        self.unk1 = unk1
        self.unk2 = unk2
        self.unk3 = unk3
        self.unk4 = unk4

        self.prev = -1
        self.next = -1

    @classmethod
    def new(cls):
        return cls(Vector3(0.0, 0.0, 0.0),
                   Vector3(0.0, 0.0, 0.0))


    @classmethod
    def from_file(cls, f):
        startoff = f.tell()
        start = Vector3(*unpack(">fff", f.read(12)))
        end = Vector3(*unpack(">fff", f.read(12)))
        unk1, unk2, unk3, unk4 = unpack(">BBBB", f.read(4))
        assert unk4 == 0
        assert unk2 == 0 or unk2 == 1
        assert unk3 == 0 or unk3 == 1
        return cls(start, end, unk1, unk2, unk3, unk4)




    def write(self, f):


        f.write(pack(">fff", self.start.x, self.start.y, self.start.z))
        f.write(pack(">fff", self.end.x, self.end.y, self.end.z))
        if not ( self.unk3 == 1 and self.unk4 == 1 ):
            f.write(pack(">BBBB", self.unk1, self.unk2, self.unk3, self.unk4))
        else:
            f.write(pack(">BBBB", 0, 0, 0, 4))

class CheckpointGroups(object):
    def __init__(self):
        self.groups = []


    @classmethod
    def from_file(cls, f, count):
        checkpointgroups = cls()

        for i in range(count):
            group = CheckpointGroup.from_file(f)
            checkpointgroups.groups.append(group)


        for group in checkpointgroups.groups:
            for i in range(group._pointcount):
                checkpoint = Checkpoint.from_file(f)
                group.points.append(checkpoint)

        return checkpointgroups




    def new_group_id(self):
        return len(self.groups)

    def points(self):
        for group in self.groups:
            for point in group.points:
                yield point

# Section 3
# Routes/Paths for cameras, objects and other things
class Route(object):
    def __init__(self):
        self.points = []
        self._pointcount = 0
        self._pointstart = 0
        self.unk1 = 0
        self.unk2 = 0

        self.used_by = []

    @classmethod
    def new(cls):
        return cls()

    @classmethod
    def new_camera(cls):

        new_route = cls()
        return new_route

    def copy(self):
        this_class = self.__class__
        obj = this_class.new()
        obj.points = self.points.copy()
        obj._pointcount = len(obj.points)
        obj.unk1 = self.unk1
        obj.unk2 = self.unk2

        return obj

    def to_object(self):
        object_route = ObjectRoute()
        self.copy_params_to_child(object_route)
        return object_route

    def to_camera(self):
        camera_route = CameraRoute()
        self.copy_params_to_child(camera_route)
        return camera_route

    def copy_params_to_child(self, new_route):
        new_route.points = self.points
        new_route.unk1 = self.unk1
        new_route.unk2 = self.unk2
        new_route.used_by = self.used_by

        return new_route

    @classmethod
    def from_file(cls, f):
        route = cls()
        route._pointcount = read_uint16(f)
        route._pointstart = read_uint16(f)
        #pad = f.read(4)
        #assert pad == b"\x00\x00\x00\x00"
        route.unk1 = read_uint32(f)
        route.unk2 = read_uint8(f)
        pad = f.read(7)
        #assert pad == b"\x00"*7

        return route

    def add_routepoints(self, points):
        for i in range(self._pointcount):
            self.points.append(points[self._pointstart+i])

    def write(self, f, pointstart):
        f.write(pack(">HH", len(self.points), pointstart))
        f.write(pack(">IB", self.unk1, self.unk2))
        f.write(b"\x04"*7)

#here for type checking - they function in the same way
class ObjectRoute(Route):
    def __init__(self):
        super().__init__()
        self.type = 0

    @classmethod
    def new(cls):
        return cls()

class CameraRoute(Route):
    def __init__(self):
        super().__init__()
        self.type = 1

    @classmethod
    def new(cls):
        return cls()



# Section 4
# Route point for use with routes from section 3
class RoutePoint(object):
    def __init__(self, position):
        self.position = position
        self.unk = 0
        self.unk2 = 0
        self.partof = None

    @classmethod
    def new(cls):
        return cls(Vector3(0.0, 0.0, 0.0))

    @classmethod
    def new_partof(cls, exis_point):
        new_point = cls(Vector3(0.0, 0.0, 0.0))
        new_point.partof = exis_point.partof
        return new_point

    @classmethod
    def from_file(cls, f):
        position = Vector3(*unpack(">fff", f.read(12)))
        point = cls(position)

        point.unk = read_uint32(f)

        padding = f.read(16)
        #assert padding == b"\x00"*16
        return point

    def copy(self):
        this_class = self.__class__
        obj = this_class.new()
        obj.partof = self.partof
        obj.unk = self.unk
        obj.unk2 = self.unk2
        return obj

    def write(self, f):
        f.write(pack(">fffI", self.position.x, self.position.y, self.position.z,
                     self.unk))
        f.write(b"\x96"*16)


class ObjectPoint(RoutePoint):
    def __init__(self, position):
        super().__init__(self, position)

class CameraPoint(RoutePoint):
    def __init__(self, position):
        super().__init__(self, position)

# Section 5
# Objects
class MapObject(object):

    can_copy = True

    def __init__(self, position, objectid):
        self.position = position
        self.scale = Vector3(1.0, 1.0, 1.0)
        self.rotation = Rotation.default()
        self.objectid = objectid
        self.route = -1
        self.unk_28 = 0
        self.unk_2a = 0
        self.presence_filter = 255
        self.presence = 0x3
        self.unk_flag = 0
        self.unk_2f = 0
        self.userdata = [0 for i in range(8)]

        self.widget = None
        self.route_info = None

    @classmethod
    def new(cls):
        return cls(Vector3(0.0, 0.0, 0.0), 1)

    @classmethod
    def default_item_box(cls):
        item_box = cls(Vector3(0.0, 0.0, 0.0), 1)
        item_box.userdata[0] = 135
        return item_box

    @classmethod
    def from_file(cls, f):
        start = f.tell()
        position = Vector3(*unpack(">fff", f.read(12)))
        scale = Vector3(*unpack(">fff", f.read(12)))
        fx, fy, fz = read_int16(f), read_int16(f), read_int16(f)
        ux, uy, uz = read_int16(f), read_int16(f), read_int16(f)

        objectid = read_uint16(f)

        obj = MapObject(position, objectid)
        obj.scale = scale
        obj.rotation = Rotation.from_mkdd_rotation(fx, fy, fz, ux, uy, uz)
        obj.route = read_int16(f)
        obj.unk_28 = read_uint16(f)
        obj.unk_2a = read_int16(f)
        obj.presence_filter = read_uint8(f)
        obj.presence = read_uint8(f)
        obj.unk_flag = read_uint8(f)
        obj.unk_2f = read_uint8(f)

        for i in range(8):
            obj.userdata[i] = read_int16(f)
        obj._size = f.tell() - start
        return obj




    def write(self, f):
        start = f.tell()
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        f.write(pack(">fff", self.scale.x, self.scale.y, self.scale.z))
        self.rotation.write(f)

        f.write(pack(">hhHh", self.objectid, self.route, self.unk_28, self.unk_2a))
        f.write(pack(">BBBB", self.presence_filter, self.presence, self.unk_flag, self.unk_2f))


        self.userdata = [0 if x is None else x for x in self.userdata]
        for i in range(8):

            f.write(pack(">h", self.userdata[i]))
        #assert f.tell() - start == self._size


    def copy(self):


        this_class = self.__class__
        obj = this_class.new()
        obj.position = Vector3(self.position.x, self.position.y, self.position.z)
        obj.rotation =  self.rotation.copy()
        obj.scale = Vector3(self.scale.x, self.scale.y, self.scale.z)
        obj.objectid = self.objectid
        obj.route = self.route
        obj.unk_28 = self.unk_28
        obj.unk_2a = self.unk_2a
        obj.presence_filter = self.presence_filter
        obj.presence = self.presence
        obj.unk_flag = self.unk_flag
        obj.unk_2f = self.unk_2f
        obj.userdata = []
        for setting in self.userdata:
            obj.userdata.append(setting)
        obj.route_info = self.route_info

        return obj

    def has_route(self):
         from widgets.data_editor import load_route_info

         if self.objectid in OBJECTNAMES:
            name = OBJECTNAMES[self.objectid]
            route_info = load_route_info(name)


            return route_info
         return None

    def set_route_info(self):
        from widgets.data_editor import load_route_info

        if self.objectid in OBJECTNAMES:
            name = OBJECTNAMES[self.objectid]
            route_info = load_route_info(name)


            self.route_info = route_info
        else:
            self.route_info = None

class MapObjects(object):
    def __init__(self):
        self.objects = []

    def reset(self):
        del self.objects
        self.objects = []

    @classmethod
    def from_file(cls, f, objectcount):
        mapobjs = cls()

        for i in range(objectcount):
            obj = MapObject.from_file(f)
            mapobjs.objects.append(obj)

        return mapobjs

# Section 6
# Kart/Starting positions
POLE_LEFT = 0
POLE_RIGHT = 1


class KartStartPoint(object):
    def __init__(self, position):
        self.position = position
        self.scale = Vector3(1.0, 1.0, 1.0)
        self.rotation = Rotation.default()
        self.poleposition = POLE_LEFT

        # 0xFF = All, otherwise refers to player who starts here
        # Example: 0 = Player 1
        self.playerid = 0xFF

        self.unknown = 0

    @classmethod
    def new(cls):
        return cls(Vector3(0.0, 0.0, 0.0))

    @classmethod
    def from_file(cls, f):
        position = Vector3(*unpack(">fff", f.read(12)))

        kstart = cls(position)
        kstart.scale = Vector3(*unpack(">fff", f.read(12)))
        kstart.rotation = Rotation.from_file(f)
        kstart.poleposition = read_uint8(f)
        kstart.playerid = read_uint8(f)
        kstart.unknown = read_uint16(f)
        #assert kstart.unknown == 0
        return kstart




    def write(self, f):
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        f.write(pack(">fff", self.scale.x, self.scale.y, self.scale.z))
        self.rotation.write(f)
        f.write(pack(">BBH", self.poleposition, self.playerid, self.unknown))

class KartStartPoints(object):
    def __init__(self):
        self.positions = []

    @classmethod
    def from_file(cls, f, count):
        kspoints = cls()

        for i in range(count):
            kstart = KartStartPoint.from_file(f)
            kspoints.positions.append(kstart)

        return kspoints


# Section 7
# Areas

AREA_TYPES = {
    0: "Shadow",
    1: "Camera",
    2: "Ceiling",
    3: "No Dead Zone",
    4: "Unknown 1",
    5: "Unknown 2",
    6: "Sound Effect",
    7: "Lighting",
}

REVERSE_AREA_TYPES = dict(zip(AREA_TYPES.values(), AREA_TYPES.keys()))


class Feather:
    def __init__(self):
        self.i0 = 0
        self.i1 = 0


class Area(object):

    can_copy = True
    def __init__(self, position):
        self.position = position
        self.scale = Vector3(1.0, 1.0, 1.0)
        self.rotation = Rotation.default()
        self.shape = 0
        self.area_type = 0
        self.camera_index = -1
        self.feather = Feather()
        self.unkfixedpoint = 0
        self.unkshort = 0
        self.shadow_id = 0
        self.lightparam_index = 0

        self.widget = None

        self.widget = None

    @classmethod
    def new(cls):
        return cls(Vector3(0.0, 0.0, 0.0))

    @classmethod
    def default(cls, type = 1):
        area = cls(Vector3(0.0, 0.0, 0.0))
        area.scale = Vector3(150, 50, 150)
        area.area_type = type
        return area

    @classmethod
    def from_file(cls, f):
        position = Vector3(*unpack(">fff", f.read(12)))

        area = cls(position)
        area.scale = Vector3(*unpack(">fff", f.read(12)))
        area.rotation = Rotation.from_file(f)
        area.shape = read_uint8(f)
        area.area_type = read_uint8(f)
        area.camera_index = read_int16(f)
        area.feather.i0 = read_uint32(f)
        area.feather.i1 = read_uint32(f)
        area.unkfixedpoint = read_int16(f)
        area.unkshort = read_int16(f)
        area.shadow_id = read_int16(f)
        area.lightparam_index = read_int16(f)

        assert area.shape in (0, 1)
        assert area.area_type in list(AREA_TYPES.keys())

        return area





    def write(self, f):
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        f.write(pack(">fff", self.scale.x, self.scale.y, self.scale.z))
        self.rotation.write(f)
        f.write(pack(">BBh", self.shape, self.area_type, self.camera_index))
        f.write(pack(">II", self.feather.i0, self.feather.i1))
        f.write(pack(">hhhh", self.unkfixedpoint, self.unkshort, self.shadow_id, self.lightparam_index))



    def copy(self):
        new_area = self.__class__.new()
        new_area.position = Vector3(self.position.x, self.position.y, self.position.z)
        new_area.rotation = self.rotation.copy()
        new_area.scale = Vector3(self.scale.x, self.scale.y, self.scale.z)
        new_area.shape = self.shape
        new_area.area_type = self.area_type
        new_area.camera_index = new_area.camera_index
        new_area.feather.i0 = self.feather.i0
        new_area.feather.i1 = self.feather.i1
        new_area.unkfixedpoint = self.unkfixedpoint
        new_area.unkshort = self.unkshort
        new_area.shadow_id = self.shadow_id
        new_area.lightparam_index = self.lightparam_index

        return new_area
class Areas(object):
    def __init__(self):
        self.areas = []

    @classmethod
    def from_file(cls, f, count):
        areas = cls()
        for i in range(count):
            areas.areas.append(Area.from_file(f))

        return areas

# Section 8
# Cameras

class FOV:
    def __init__(self):
        self.start = 0
        self.end = 0


class Shimmer:
    def __init__(self):
        self.z0 = 0
        self.z1 = 0


class Camera(object):
    can_copy = True
    route_info = 2
    def __init__(self, position):
        self.position = position
        self.position2 = Vector3(0.0, 0.0, 0.0)
        self.position3 = Vector3(0.0, 0.0, 0.0)
        self.rotation = Rotation.default()

        self.chase = 0
        self.camtype = 0

        self.fov = FOV()

        self.camduration = 0
        self.startcamera = 0

        self.shimmer = Shimmer()
        self.route = -1
        self.routespeed = 0
        self.nextcam = -1
        self.name = "null"

        self.widget = None
        self.used_by = []



        self.widget = None

    @classmethod
    def new(cls):
        return cls(Vector3(0.0, 0.0, 0.0))
    @classmethod
    def default(cls, type = 1):
        camera = cls(Vector3(0.0, 0.0, 0.0))
        camera.camtype = type
        camera.fov.start = 40
        camera.fov.end = 50

        if (type == 1 ):
            camera.chase = 1
            camera.shimmer.z0 = 4000
            camera.shimmer.z1 = 4060
            camera.routespeed = 20

        return camera


    @classmethod
    def from_file(cls, f):
        position = Vector3(*unpack(">fff", f.read(12)))

        cam = cls(position)
        cam.rotation = Rotation.from_file(f)
        cam.position2 = Vector3(*unpack(">fff", f.read(12)))
        cam.position3 = Vector3(*unpack(">fff", f.read(12)))
        cam.chase = read_uint8(f)
        cam.camtype = read_uint8(f)
        cam.fov.start = read_uint16(f)
        cam.camduration = read_uint16(f)
        cam.startcamera = read_uint16(f)
        cam.shimmer.z0 = read_uint16(f)
        cam.shimmer.z1 = read_uint16(f)
        cam.route = read_int16(f)
        cam.routespeed = read_uint16(f)
        cam.fov.end = read_uint16(f)
        cam.nextcam = read_int16(f)
        cam.name = str(f.read(4), encoding="ascii")

        return cam



    def copy(self):
        new_camera = self.__class__.new()
        new_camera.position = Vector3(self.position.x, self.position.y, self.position.z)
        new_camera.position2 = Vector3(self.position2.x, self.position2.y, self.position2.z)
        new_camera.position3 = Vector3(self.position3.x, self.position3.y, self.position3.z)
        new_camera.rotation = self.rotation.copy()

        new_camera.chase = self.chase
        new_camera.camtype = self.camtype
        new_camera.fov.start = self.fov.start
        new_camera.fov.end = self.fov.end
        new_camera.camduration = self.camduration
        new_camera.startcamera = self.startcamera
        new_camera.shimmer.z0 = self.shimmer.z0
        new_camera.shimmer.z1 = self.shimmer.z1
        new_camera.route = self.route
        new_camera.routespeed = self.routespeed
        new_camera.nextcam = self.nextcam
        new_camera.name = self.name


        return new_camera

    #write to bol
    def write(self, f):

        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        self.rotation.write(f)
        f.write(pack(">fff", self.position2.x, self.position2.y, self.position2.z))
        f.write(pack(">fff", self.position3.x, self.position3.y, self.position3.z))

        if self.camtype in [0, 1, 2, 3]:
            f.write(pack(">B", self.chase))
        else:
            f.write(pack(">B", 0))
        f.write(pack(">BHHH",  self.camtype, self.fov.start, self.camduration, self.startcamera))
        f.write(pack(">HHhHHh",
                        self.shimmer.z0, self.shimmer.z1, self.route,
                        self.routespeed, self.fov.end, self.nextcam))
        assert len(self.name) == 4
        f.write(bytes(self.name, encoding="ascii"))


    @classmethod
    def new_type_0(cls):
        pass

    @classmethod
    def new_type_1(cls):
        pass

    @classmethod
    def new_type_7(cls):
        pass

    @classmethod
    def new_type_8(cls):
        cam =  cls(Vector3(-860.444, 6545.688, 3131.74))
        cam.rotation = Rotation.from_euler(Vector3(0, 0, 0))
        cam.position2 = Vector3(160, 6, 0)
        cam.position3 = Vector3(-20, -20, 450)
        cam.chase = 0
        cam.camtype = 8
        cam.fov.start = 85
        cam.camduration = 1800
        cam.startcamera = 0
        cam.shimmer.z0 = 0
        cam.shimmer.z1 = 0
        cam.route = -1
        cam.routespeed = 1
        cam.fov.end = 35
        cam.nextcam = -1
        cam.name = "para"

        return cam

    def has_route(self):
        return (self.camtype in [1, 3, 4, 5])

# Section 9
# Jugem Points
class JugemPoint(object):
    def __init__(self, position):
        self.position = position
        self.rotation = Rotation.default()
        self.respawn_id = 0
        self.unk1 = 0
        self.unk2 = 0
        self.unk3 = 0

        self.widget = None

    @classmethod
    def new(cls):
        return cls(Vector3(0.0, 0.0, 0.0))

    @classmethod
    def from_file(cls, f):
        position = Vector3(*unpack(">fff", f.read(12)))
        jugem = cls(position)
        jugem.rotation = Rotation.from_file(f)
        jugem.respawn_id = read_uint16(f)
        jugem.unk1 = read_int16(f)
        jugem.unk2 = read_int16(f)
        jugem.unk3 = read_int16(f)

        return jugem

    def write(self, f):
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        self.rotation.write(f)
        f.write(pack(">HHhh", self.respawn_id, self.unk1, self.unk2, self.unk3))



# Section 10
# LightParam
class LightParam(object):
    def __init__(self):
        self.color1 = ColorRGBA(0x64, 0x64, 0x64, 0xFF)
        self.color2 = ColorRGBA(0x64, 0x64, 0x64, 0x00)
        self.position = Vector3(0.0, 0.0, 0.0)



    @classmethod
    def new(cls):
        return cls()

    @classmethod
    def from_file(cls, f):
        lp = cls()
        lp.color1 = ColorRGBA.from_file(f)
        lp.unkpositionvec = Vector3(*unpack(">fff", f.read(12)))
        lp.color2 = ColorRGBA.from_file(f)

        return lp

    def write(self, f):
        self.color1.write(f)
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        self.color2.write(f)


# Section 11
# MG (MiniGame?)
class MGEntry(object):
    def __init__(self):
        self.rabbitWinSec = 0
        self.rabbitMinSec = 0
        self.rabbitDecSec = 0
        self.unk4 = 0

    @classmethod
    def new(cls):
        return cls()

    @classmethod
    def from_file(cls, f):
        mgentry = MGEntry()
        mgentry.rabbitWinSec = read_int16(f)
        mgentry.rabbitMinSec = read_int16(f)
        mgentry.rabbitDecSec = read_int16(f)
        mgentry.unk4 = read_int16(f)

        return mgentry

    def write(self, f):
        f.write(pack(">hhhh", self.rabbitWinSec, self.rabbitMinSec, self.rabbitDecSec, self.unk4))


class BOL(object):
    def __init__(self):
        self.bol = True


        self.roll = 0
        self.rgb_ambient = ColorRGB(250, 250, 250)
        self.rgba_light = ColorRGBA(0xFF, 0xFF, 0xFF, 0xFF)
        self.lightsource = Vector3(0.0, 0.0, 0.0)
        self.fog_type = 0
        self.fog_color = ColorRGB(0x64, 0x64, 0x64)
        self.fog_startz = 8000.0
        self.fog_endz = 230000.0
        self.lod_bias = 0
        self.dummy_start_line = 0
        self.snow_effects = 0
        self.shadow_opacity = 0
        self.starting_point_count = 0
        self.sky_follow = 0

        self.shadow_color = ColorRGB(0x00, 0x00, 0x00)


        self.sections = {}

        self.lap_count = 3
        self.music_id = 0x21

        self.enemypointgroups = EnemyPointGroups()
        self.checkpoints = CheckpointGroups()
        self.routes = ObjectContainer()

        self.objects = MapObjects()
        self.kartpoints = KartStartPoints()
        self.areas = Areas()
        self.cameras = ObjectContainer()
        self.cameraroutes = ObjectContainer()

        self.respawnpoints = ObjectContainer()

        self.lightparams = ObjectContainer()

        self.mgentries = ObjectContainer()



    def set_assoc(self):
        self.routes.assoc = ObjectRoute
        self.cameraroutes.assoc = CameraRoute
        self.cameras.assoc = Camera
        self.respawnpoints.assoc = JugemPoint
        self.lightparams.assoc = LightParam
        self.mgentries.assoc = MGEntry
        self.areas.assoc = Area

    @classmethod
    def make_useful(cls):
        bol = cls()
        bol.enemypointgroups.groups.append(EnemyPointGroup.new())
        bol.checkpoints.groups.append(CheckpointGroup.new() )
        bol.kartpoints.positions.append( KartStartPoint.new() )
        bol.cameras.append( Camera.new_type_8() )
        bol.lightparams.append(LightParam.new())

        bol.set_assoc()

        return bol


    def objects_with_position(self):
        for group in self.enemypointgroups.groups.values():
            for point in group.points:
                yield point

        for route in self.routes:
            for point in route.points:
                yield point
        for route in self.cameraroutes:
            for point in route.points:
                yield point

    def objects_with_2positions(self):
        for group in self.checkpoints.groups:
            for point in group.points:
                yield point

    def objects_with_rotations(self):
        for object in self.objects.objects:
            assert object is not None
            yield object

        for kartpoint in self.kartpoints.positions:
            assert kartpoint is not None
            yield kartpoint

        for area in self.areas.areas:
            assert area is not None
            yield area

        for camera in self.cameras:
            assert camera is not None
            yield camera

        for respawn in self.respawnpoints:
            assert respawn is not None
            yield respawn

    def get_all_objects(self):
        objects = []

        for group in self.enemypointgroups.groups:
            objects.append(group)
            objects.extend(group.points)

        for group in self.checkpoints.groups:
            objects.append(group)
            objects.extend(group.points)

        for route in self.routes:
            objects.append(route)
            objects.extend(route.points)

        objects.extend(self.objects.objects)
        objects.extend(self.kartpoints.positions)
        objects.extend(self.areas.areas)
        objects.extend(self.cameras)
        objects.extend(self.respawnpoints)
        objects.extend(self.lightparams)
        objects.extend(self.mgentries)

        return objects

    @classmethod
    def from_file(cls, f):
        bol = cls()
        magic = f.read(4)
        #assert magic == b"0015" or magic == b"0012"
        old_bol = magic == b"0012"

        bol.roll = read_uint8(f)
        bol.rgb_ambient = ColorRGB.from_file(f)

        if not old_bol:
            bol.rgba_light = ColorRGBA.from_file(f)
            bol.lightsource = Vector3(read_float(f), read_float(f), read_float(f))

        bol.lap_count = read_uint8(f)
        bol.music_id = read_uint8(f)

        sectioncounts = {}
        for i in (ENEMYITEMPOINT, CHECKPOINT, OBJECTS, AREA, CAMERA, ROUTEGROUP, RESPAWNPOINT):
            sectioncounts[i] = read_uint16(f)

        bol.fog_type = read_uint8(f)
        bol.fog_color = ColorRGB.from_file(f)

        bol.fog_startz = read_float(f)
        bol.fog_endz = read_float(f)
        bol.lod_bias = read_uint8(f)
        bol.dummy_start_line = read_uint8(f)
        #assert bol.lod_bias in (0, 1)
        #assert bol.dummy_start_line in (0, 1)
        bol.lod_bias = min(1, bol.lod_bias)
        bol.dummy_start_line = min(1, bol.dummy_start_line)
        bol.snow_effects = read_uint8(f)
        bol.shadow_opacity = read_uint8(f)
        bol.shadow_color = ColorRGB.from_file(f)
        bol.starting_point_count = read_uint8(f)
        bol.sky_follow = read_uint8(f)
        #assert bol.sky_follow in (0, 1)
        bol.sky_follow = min(1, bol.sky_follow)

        sectioncounts[LIGHTPARAM] = read_uint8(f)
        sectioncounts[MINIGAME] = read_uint8(f)
        padding = read_uint8(f)
        #assert padding == 0

        filestart = read_uint32(f)
        assert filestart == 0

        sectionoffsets = {}
        for i in range(11):
            sectionoffsets[i+1] = read_uint32(f)

        padding = f.read(12) # padding
        #assert padding == b"\x00"*12
        endofheader = f.tell()


        #calculated_count = (sectionoffsets[CHECKPOINT] - sectionoffsets[ENEMYITEMPOINT])//0x20
        #assert sectioncounts[ENEMYITEMPOINT] == calculated_count
        f.seek(sectionoffsets[ENEMYITEMPOINT])
        bol.enemypointgroups = EnemyPointGroups.from_file(f, sectioncounts[ENEMYITEMPOINT], old_bol)

        f.seek(sectionoffsets[CHECKPOINT])
        bol.checkpoints = CheckpointGroups.from_file(f, sectioncounts[CHECKPOINT])

        f.seek(sectionoffsets[ROUTEGROUP])
        bol.routes = ObjectContainer.from_file(f, sectioncounts[ROUTEGROUP], Route)

        f.seek(sectionoffsets[ROUTEPOINT])
        routepoints = []
        count = (sectionoffsets[OBJECTS] - sectionoffsets[ROUTEPOINT])//0x20
        for i in range(count):
            routepoints.append(RoutePoint.from_file(f))

        for route in bol.routes:
            route.add_routepoints(routepoints)

        f.seek(sectionoffsets[OBJECTS])
        bol.objects = MapObjects.from_file(f, sectioncounts[OBJECTS])

        f.seek(sectionoffsets[KARTPOINT])
        bol.kartpoints = KartStartPoints.from_file(f, (sectionoffsets[AREA] - sectionoffsets[KARTPOINT])//0x28)
        #assert len(bol.kartpoints.positions) == bol.starting_point_count

        f.seek(sectionoffsets[AREA])
        bol.areas = Areas.from_file(f, sectioncounts[AREA])

        f.seek(sectionoffsets[CAMERA])
        bol.cameras = ObjectContainer.from_file(f, sectioncounts[CAMERA], Camera)

        f.seek(sectionoffsets[RESPAWNPOINT])
        bol.respawnpoints = ObjectContainer.from_file(f, sectioncounts[RESPAWNPOINT], JugemPoint)

        #order by id
        bol.respawnpoints.sort(key=lambda x: x.respawn_id)

        f.seek(sectionoffsets[LIGHTPARAM])

        bol.lightparams = ObjectContainer.from_file(f, sectioncounts[LIGHTPARAM], LightParam)

        f.seek(sectionoffsets[MINIGAME])
        bol.mgentries = ObjectContainer.from_file(f, sectioncounts[MINIGAME], MGEntry)

        bol.fixup_file()



        bol.set_assoc()

        return bol



    def fixup_file(self):
        #set all the used by stuff
        for object in self.objects.objects:
            object.set_route_info()
            if object.route != -1:
                self.routes[object.route].used_by.append(object)
        for camera in self.cameras:
            if camera.route != -1 and camera.route < len(self.routes):
                self.routes[camera.route].used_by.append(camera)
            else:
                camera.route = -1
        for area in self.areas.areas:
            if area.camera_index != -1 and area.camera_index < len(self.cameras):
                self.cameras[area.camera_index].used_by.append(area)

        #split camera and object routes
        to_split = []
        for route in self.routes:
            has_object = False
            has_camera = False
            for object in route.used_by:
                if isinstance(object, MapObject):
                    has_object = True
                elif isinstance(object, Camera):
                    has_camera = True
            if has_camera and has_object:
                to_split.append(route)

        new_route_idx = len(self.routes)

        for route in to_split :
            # we know that these have both objects and cameras
            new_route = route.copy()
            new_route.used_by = filter(lambda thing: isinstance(thing, Camera), route.used_by)
            route.used_by = filter(lambda thing: isinstance(thing, MapObject), route.used_by)

            bol.routes.append(new_route)
            for obj in new_route.used_by:
                obj.route = new_route_idx
                new_route_idx += 1

        #now that everything is split, we can spilt into cam routes and non cam routes
        object_routes = ObjectContainer()
        camera_routes = ObjectContainer()
        for route in self.routes:
            if len(route.used_by) > 0:
                if isinstance(route.used_by[0], Camera):
                    camera_routes.append(route.to_camera())
                elif isinstance(route.used_by[0], MapObject):
                    object_routes.append(route.to_object())
        self.routes = object_routes
        self.cameraroutes = camera_routes

        #set used by again:
        for i, route in enumerate(self.routes):
            for object in route.used_by:
                object.route = i
            for point in route.points:
                point.partof = route
        for i, route in enumerate(self.cameraroutes):
            for object in route.used_by:
                object.route = i
            for point in route.points:
                point.partof = route

    @classmethod
    def from_bytes(cls, data: bytes) -> 'BOL':
        return BOL.from_file(BytesIO(data))

    def write(self, f):
        #f.write(b"0015")
        f.write(b"0014")
        f.write(pack(">B", self.roll))
        self.rgb_ambient.write(f)
        self.rgba_light.write(f)
        f.write(pack(">fff", self.lightsource.x, self.lightsource.y, self.lightsource.z))
        f.write(pack(">BB", self.lap_count, self.music_id))

        enemypoints = 0
        for group in self.enemypointgroups.groups:
            enemypoints += len(group.points)
        write_uint16(f, enemypoints)
        write_uint16(f, len(self.checkpoints.groups))
        write_uint16(f, len(self.objects.objects))
        write_uint16(f, len(self.areas.areas))
        write_uint16(f, len(self.cameras))
        write_uint16(f, len(self.routes) + len(self.cameraroutes))
        write_uint16(f, len(self.respawnpoints))

        f.write(pack(">B", self.fog_type))
        self.fog_color.write(f)
        f.write(pack(">ffBBBB",
                self.fog_startz, self.fog_endz,
                self.lod_bias, self.dummy_start_line, self.snow_effects, self.shadow_opacity))
        self.shadow_color.write(f)
        f.write(pack(">BB", len(self.kartpoints.positions), self.sky_follow))
        f.write(pack(">BB", len(self.lightparams), len(self.mgentries)))
        f.write(pack(">B", 0))  # padding

        f.write(b"\x00"*4) # Filestart 0

        offset_start = f.tell()
        offsets = []
        for i in range(11):
            f.write(b"FOOB") # placeholder for offsets
        f.write(b"\x12"*12) # padding

        offsets.append(f.tell())
        for group in self.enemypointgroups.groups:
            #group = self.enemypointgroups.groups[groupindex]
            for point in group.points:
                point.group = group.id
                point.write(f)

        offsets.append(f.tell())
        for group in self.checkpoints.groups:
            group.write(f)
        for group in self.checkpoints.groups:
            for point in group.points:
                point.write(f)

        offsets.append(f.tell())

        routes, cameras = self.combine_routes()

        index = 0
        for route in routes:
            route.write(f, index)
            index += len(route.points)

        offsets.append(f.tell())
        for route in routes:
            for point in route.points:
                point.write(f)

        offsets.append(f.tell())
        for object in self.objects.objects:
            object.write(f)

        offsets.append(f.tell())
        for startpoint in self.kartpoints.positions:
            startpoint.write(f)

        offsets.append(f.tell())
        for area in self.areas.areas:
            area.write(f)

        offsets.append(f.tell())
        for camera in cameras:
            camera.write(f)

        offsets.append(f.tell())
        for respawnpoint in self.respawnpoints:
            respawnpoint.write(f)

        offsets.append(f.tell())
        for lightparam in self.lightparams:
            lightparam.write(f)

        offsets.append(f.tell())
        for mgentry in self.mgentries:
            mgentry.write(f)
        assert len(offsets) == 11
        f.seek(offset_start)
        for offset in offsets:
            f.write(pack(">I", offset))

    def to_bytes(self) -> bytes:
        f = BytesIO()
        self.write(f)
        return f.getvalue()

    def combine_routes(self):
        routes = ObjectContainer()
        cameras = ObjectContainer()

        num_obj = len(self.routes)

        for route in self.routes:
            routes.append(route)
        for route in self.cameraroutes:
            routes.append(route)
        for camera in self.cameras:
            new_cam = camera.copy()
            if new_cam.route != -1:
                new_cam.route += num_obj
            cameras.append(new_cam)

        return routes, cameras

    def auto_qol_all(self):
        # clear checkpoints
        for checkgroup in self.checkpoints.groups:
            checkgroup.points.clear()
        self.checkpoints.groups.clear()

        self.enemypointgroups.assign_prev_next()

        for i, group in enumerate( self.enemypointgroups.groups ):
            new_cp_group = CheckpointGroup(i)
            new_cp_group.prevgroup = group.prev
            new_cp_group.nextgroup = group.next

            self.checkpoints.groups.append( new_cp_group )

            #group = self.enemypointgroups.groups[groupindex]
            for j, point in enumerate( group.points ):
                draw_cp = False
                if i == 0 and j == 0:
                    draw_cp = True
                    #should both be vector3
                    central_point = self.kartpoints.positions[0].position
                    left_vector = self.kartpoints.positions[0].rotation.get_vectors()[2]

                elif (i == 0 and j % 2 == 0 and len(group.points) > j + 1) or (i > 0 and j % 2 == 1 and len(group.points) > j + 1):
                #elif (i == 0  and len(group.points) > j + 1) or (i > 0 and len(group.points) > j + 1):
                    draw_cp = True
                    central_point = point.position

                    deltaX = group.points[j+1].position.x - group.points[j-1].position.x
                    deltaZ = group.points[j+1].position.z - group.points[j-1].position.z

                    left_vector = Vector3( -1 * deltaZ, 0, deltaX   ) * -1

                    left_vector.normalize()


                if draw_cp:

                    first_point = [central_point.x + 3500 * left_vector.x, 0, central_point.z + 3500 * left_vector.z]
                    second_point = [central_point.x - 3500 * left_vector.x, 0, central_point.z - 3500 * left_vector.z]

                    new_checkpoint = Checkpoint.new()
                    new_checkpoint.start = Vector3( *first_point)
                    new_checkpoint.end = Vector3(*second_point)
                    new_cp_group.points.append( new_checkpoint)

        self.remove_unused_cameras()
        self.remove_unused_routes()

    def set_checkpoint_respawns():

        for checkgroup in self.checkpoints.groups:
            for checkpoint in checkgroup.points:
                closest_idx = -1
                closest_dis = 9999999999999999
                for i, point in enumerate( self.respawnpoints ):
                    center = (checkpoint.start + checkpoint.end ) / 2.0
                    dis = point.position.distance(center)
                    if dis < closest_dis:
                        closest_idx = i
                        closest_dis = dis
                checkpoint.unk1 = closest_idx


        pass

    def reset_routes(self, start_at = 0):

        self.reset_object_routes(start_at)
        self.reset_camera_routes(start_at)

    def reset_object_routes(self, start_at = 0):
        for route_index in range(start_at, len(self.routes) ):
            for object in self.routes[route_index].used_by:
                object.route = route_index

    def reset_camera_routes(self, start_at = 0):
        for route_index in range(start_at, len(self.cameraroutes) ):
            for object in self.cameraroutes[route_index].used_by:
                object.route = route_index


    def remove_unused_routes(self):
        self.remove_unused_object_routes()
        self.remove_unused_camera_routes()

    def remove_unused_object_routes(self):
        to_remove = []
        for i, route in enumerate(self.routes):
            if len(route.used_by) == 0:
                to_remove.append(i)
        to_remove.sort()
        to_remove.reverse()
        for rem_index in to_remove:
            self.routes.pop(rem_index)
        self.reset_object_routes()

    def remove_unused_camera_routes(self):
        to_remove = []
        for i, route in enumerate(self.cameraroutes):
            if len(route.used_by) == 0:
                to_remove.append(i)
        to_remove.sort()
        to_remove.reverse()
        for rem_index in to_remove:
            self.cameraroutes.pop(rem_index)
        self.reset_camera_routes()

    def remove_unused_cameras(self):
        used = []
        opening_cams = []

        #type 8 stays

        for camera in self.cameras:
            if camera.camtype == 8:
                used.append(camera)

        next_cam = -1
        for i,camera in enumerate(self.cameras):
            if camera.startcamera == 1:
                next_cam = i
                opening_cams.append(camera)


        while next_cam != -1 and next_cam < len(self.cameras):
            next_camera = self.cameras[next_cam]
            if next_camera in used:
                break
            used.append(next_camera)
            opening_cams.append(next_camera)
            next_cam = next_camera.nextcam

        #now iterate through area
        for area in self.areas.areas:
            if area.camera_index != -1 and area.camera_index < len(self.cameras):
                used.append( self.cameras[area.camera_index]  )


        #deleting stuff
        for i in range( len(self.cameras) -1, -1, -1):
            cam_to_del = self.cameras[i]
            if not cam_to_del in used:
                if cam_to_del.route != -1 and cam_to_del.route < len(self.cameraroutes):
                    self.cameraroutes[cam_to_del.route].used_by.remove(cam_to_del)
                self.cameras.remove(cam_to_del)

        for i, camera in enumerate (self.cameras):
            for area in camera.used_by:
                area.camera_index = i

        #deal with starting cams
        curr_cam = opening_cams[0]
        for i in range(1, len(opening_cams)):
            next_idx = self.cameras.index( opening_cams[i] )
            curr_cam.nextcam = next_idx
            curr_cam = self.cameras[next_idx]

        #figure out which cameras to remove
        #then

        pass

    def reassign_one_respawn(self, rsp : JugemPoint):
        min_dis = 999999999999999999
        min_idx = 0
        idx = 0

        if len(self.enemypointgroups.groups ) > 0:
            for group in self.enemypointgroups.groups:
                for point in group.points:
                    this_dis =  point.position.distance(rsp.position)
                    if this_dis < min_dis:
                        min_dis = this_dis
                        min_idx = idx
                    idx += 1
        rsp.unk1 = min_idx

    def reassign_respawns(self):
        for rsp in self.respawnpoints:
            self.reassign_one_respawn(rsp)


    def get_route_container(self, obj):
        if isinstance(obj, (CameraRoute, Camera)):
            return self.cameraroutes
        else:
            return self.routes

    def get_route_for_obj(self, obj):
        if isinstance(obj, CameraRoute):
            return CameraRoute()
        else:
            return ObjectRoute()


with open("lib/mkddobjects.json", "r") as f:
    tmp = json.load(f)
    OBJECTNAMES = {}
    for key, val in tmp.items():
        OBJECTNAMES[int(key)] = val
    del tmp



REVERSEOBJECTNAMES = OrderedDict()
valpairs = [(x, y) for x, y in OBJECTNAMES.items()]
valpairs.sort(key=lambda x: x[1])

for key, val in valpairs:
    REVERSEOBJECTNAMES[OBJECTNAMES[key]] = key

with open("lib/music_ids.json", "r") as f:
    tmp = json.load(f)
    MUSIC_IDS = {}
    for key, val in tmp.items():
        MUSIC_IDS[int(key)] = val
    del tmp

REVERSE_MUSIC_IDS = OrderedDict()
for key in sorted(MUSIC_IDS.keys()):
    REVERSE_MUSIC_IDS[MUSIC_IDS[key]] = key
SWERVE_IDS = {
    -3: "To the left (-3)",
    -2: "To the left (-2)",
    -1: "To the left (-1)",
    0: "",
    1: "To the right (1)",
    2: "To the right (2)",
    3: "To the right (3)",
}
REVERSE_SWERVE_IDS = OrderedDict()
for key in sorted(SWERVE_IDS.keys()):
    REVERSE_SWERVE_IDS[SWERVE_IDS[key]] = key

def get_full_name(id):
    if id not in OBJECTNAMES:
        OBJECTNAMES[id] = "Unknown {0}".format(id)
        REVERSEOBJECTNAMES[OBJECTNAMES[id]] = id
        #return
    #else:
    return OBJECTNAMES[id]




def temp_add_invalid_id(id):
    if id not in OBJECTNAMES:
        name = get_full_name(id)
        OBJECTNAMES[id] = name
        REVERSEOBJECTNAMES[name] = id


if __name__ == "__main__":
    with open("mario_course.bol", "rb") as f:
        bol = BOL.from_file(f)

    with open("mario_course_new.bol", "wb") as f:
        bol.write(f)

    with open("mario_course_new.bol", "rb") as f:
        newbol = BOL.from_file(f)

    with open("mario_course_new2.bol", "wb") as f:
        newbol.write(f)