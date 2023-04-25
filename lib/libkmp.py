import json
from struct import unpack, pack
from numpy import ndarray, array, arctan
from math import cos, sin, atan2
from .vectors import Vector3, Vector2
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

rotation_constant = 100
def write_padding(f, multiple):
    next_aligned = (f.tell() + (multiple - 1)) & ~(multiple - 1)

    diff = next_aligned - f.tell()

    for i in range(diff):
        pos = i % len(PADDING)
        f.write(PADDING[pos:pos + 1])

class Rotation(object):
    def __init__(self, x, y, z):
        self.mtx = ndarray(shape=(4,4), dtype=float, order="F")
        self.x = x % 360
        self.y = y % 360
        self.z = z % 360

    def rotate_around_x(self, degrees):
        self.x += degrees * rotation_constant
        self.x = self.x % 360

    def rotate_around_y(self, degrees):
        self.y += degrees * rotation_constant
        self.y = self.y % 360

    def rotate_around_z(self, degrees):
        self.z += degrees  * rotation_constant
        self.z += self.z % 360

    def get_rotation_matrix( self ):

        iden = [
			[1, 0, 0, 0],
			[0, 1, 0, 0],
			[0, 0, 1, 0],
			[0, 0, 0, 1]
		]
        iden = numpy.matmul(iden, self.get_rotation_from_vector( Vector3(0.0, 0.0, 0.1), 90))
        iden = numpy.matmul(iden, self.get_rotation_from_vector( Vector3(1.0, 0.0, 0.0), -self.x   ))
        iden = numpy.matmul(iden, self.get_rotation_from_vector( Vector3(0.0, 0.0, 1.0), -self.y   ))
        iden = numpy.matmul(iden, self.get_rotation_from_vector( Vector3(0.0, 1.0, 0.0), self.z   ))

        return iden

    def get_rotation_from_vector(self, vec, degrees):
        x = vec.x
        y = vec.y
        z = vec.z
        c = numpy.cos( numpy.deg2rad(degrees) )
        s = numpy.sin( numpy.deg2rad(degrees) )
        t = 1 - c

        return [
			[t*x*x + c,    t*x*y - z*s,  t*x*z + y*s, 0],
			[t*x*y + z*s,  t*y*y + c,    t*y*z - x*s, 0],
			[t*x*z - y*s,  t*y*z + x*s,  t*z*z + c,   0],
			[          0,            0,          0,   1]
		]

    @classmethod
    def default(cls):
        return cls(0, 0, 0)
    @classmethod
    def from_file(cls, f, printe = False):
        euler_angles = list(unpack(">fff", f.read(12)))

        return cls(*euler_angles)

    def get_vectors(self):

        y = self.y - 90
        y, z = self.z * -1, self.y

        r = R.from_euler('xyz', [self.x, y, z], degrees=True)
        vecs = r.as_matrix()
        vecs = vecs.transpose()

        mtx = ndarray(shape=(4,4), dtype=float, order="F")
        mtx[0][0:3] = vecs[0]
        mtx[1][0:3] = vecs[1]
        mtx[2][0:3] = vecs[2]
        mtx[3][0] = mtx[3][1] = mtx[3][2] = 0.0
        mtx[3][3] = 1.0

        left = Vector3(-mtx[0][0], mtx[0][2], mtx[0][1])
        up = Vector3(-mtx[2][0], mtx[2][2], mtx[2][1])
        forward = Vector3(-mtx[1][0], mtx[1][2], mtx[1][1])

        return forward, up, left

    def write(self, f):
        f.write(pack(">fff", self.x, self.y, self.z) )

    def get_render(self):

        return self.get_rotation_matrix()

    def get_euler(self):

        vec = [self.x % 360, self.y % 360 , self.z % 360]

        return vec

    @classmethod
    def from_euler(cls, degs):
        rotation = cls(degs.x, degs.y, degs.z )


        return rotation


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

    @classmethod
    def from_file(cls, f, count, objcls):
        container = cls()


        for i in range(count):
            obj = objcls.from_file(f)
            container.append(obj)

        return container

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

class KMPPoint(object):
    def __init__(self):
        pass

class PointGroup(object):
    def __init__(self):
        self.points = []
        self.prevgroup = []
        self.nextgroup = []

    def insert_point(self, enemypoint, index=-1):
        self.points.insert(index, enemypoint)

    def move_point(self, index, targetindex):
        point = self.points.pop(index)
        self.points.insert(targetindex, point)

    def copy_group(self, group):
        for point in self.points:
            #new_point = deepcopy(point)
            group.points.append(point)

        group.prevgroup = self.prevgroup.copy()
        group.nextgroup = self.nextgroup.copy()

        return group

    def copy_group_after(self, point, new_group):
        pos = self.points.index(point)

        # Check if the element is the last element
        if not len(self.points)-1 == pos:
            for point in self.points[pos+1:]:
                new_group.points.append(point)

        #this is the new group
        new_group.nextgroup = self.nextgroup.copy()
        new_group.prevgroup = [self]

        #this is the current group
        self.nextgroup = [new_group]
        self.prevgroup = [new_group if group == self else group for group in self.prevgroup]

        return new_group

    def remove_after(self, point):
        pos = self.points.index(point)
        self.points = self.points[:pos+1]

    def copy_into_group(self, group):
        self.points.extend(group.points)

    def num_prev(self):
        return len(self.prevgroup)

    def num_next(self):
        return len(self.nextgroup)

    def add_new_prev(self, new_group):
        if new_group is None or self.num_prev() == 6 or new_group in self.prevgroup:
            return False
        self.prevgroup.append(new_group)

    def add_new_next(self, new_group):
        if new_group is None or self.num_next() == 6 or new_group in self.nextgroup:
            return False
        self.nextgroup.append(new_group)

    def remove_prev(self, group):
        if group in self.prevgroup:
            self.prevgroup.remove(group)

    def remove_next(self, group):
        if group in self.nextgroup:
            self.nextgroup.remove(group)

class PointGroups(object):
    def __init__(self):
        self.groups = []
        self._group_ids = {}

    def points(self):
        for group in self.groups:
            for point in group.points:
                yield point

    def split_group(self, group : PointGroup, point : KMPPoint):
        new_group = self.get_new_group()
        new_group = group.copy_group_after(point, new_group)

        self.groups.append(new_group)
        group.remove_after(point)

        for other_group in self.groups:
            if group in other_group.prevgroup:
                other_group.prevgroup = [new_group if grp == group else grp for grp in other_group.prevgroup ]

    def find_group_of_point(self, point):
        for i, group in enumerate(self.groups):
            for j, curr_point in enumerate(group.points):
                if point == curr_point:
                    return i, group, j
        return None, None, None

    def merge_groups(self):
        #print("new merge cycle")
        if len(self.groups) < 2:
            return

        first_group = self.groups[0]
        i = 0
        while i < len(self.groups):
            if len(self.groups) < 2:
                return

            group = self.groups[i]
            #print("compare the ids, they should be the same", i, group.id)
            #if this group only has one next, and the nextgroup only has one prev, they can be merged
            if group.num_next() == 1 and group.nextgroup[0].num_prev() == 1:
                if first_group in group.nextgroup:
                    #print("do not merge with the starte")
                    i += 1 #do not merge with the start
                    continue
                del_group = group.nextgroup[0]
                if group == del_group:
                    print("ERROR: TRYING TO MERGE INTO ITSELF", i)
                    return
                    #continue

                group.copy_into_group( del_group )

                self.groups.remove(del_group)

                #replace this group's next with the deleted group's next
                group.nextgroup = del_group.nextgroup.copy()

                for this_group in self.groups:
                    #replace links to the deleted group with the group it was merged into
                    this_group.prevgroup = [ group if grp == del_group else grp for grp in this_group.prevgroup]
            else:
                i += 1

    def get_new_point(self):
        return KMPPoint.new()

    def get_new_group(self):
        return PointGroup.new()

    def add_new_group(self):
        new_group = self.get_new_group()
        self.groups.append( new_group )

        if len(self.groups) == 1:
            new_group.add_new_next(new_group)
            new_group.add_new_prev(new_group)

    def remove_group(self, del_group, merge = True):
        self.groups.remove(del_group)

        for group in self.groups :

            #remove previous links to the deleted group
            group.prevgroup = [ grp for grp in group.prevgroup if grp != del_group]
            group.nextgroup = [ grp for grp in group.nextgroup if grp != del_group]


        if merge:
            self.merge_groups()

        if len(self.groups) == 1:
            self.groups[0].add_new_next(self.groups[0])
            self.groups[0].add_new_prev(self.groups[0])

    def remove_point(self, point):
        group_idx, group, point_idx = self.find_group_of_point(point)
        if len(group.points) == 1:
            self.remove_group(group)
        else:
            group.points.remove(point)

    def remove_unused_groups(self):
        #remove empty
        to_delete = [ group for group in self.groups if len(group.points) == 0 ]
        for group in to_delete:
            self.remove_group(group)

        #remove those that do not follow the main path
        to_visit = [0]
        visited = []

        while len(to_visit) > 0:

            idx = to_visit[0]
            if idx in visited:
                to_visit.pop(0)
            visited.append(idx)

            to_visit.extend( [grp for grp in to_visit.nextgroup if grp not in visited] )

        unused_groups = [grp for grp in self.groups if grp not in visited]
        for group in unused_groups:
            if group in self.groups:
                #do not merge until the end
                self.remove_group( group, False   )
        self.merge_groups()

    def num_total_points(self):
        return sum( [len(group.points) for group in self.groups]  )

    def get_point_from_index(self, idx):
        for group in self.groups:
            points_in_group = len(group.points)
            if idx < points_in_group:
                return group.points[idx]
            idx -= points_in_group
        return None

    def get_index_from_point(self, point):
        id = 0
        for group in self.groups:
            for curr_point in group.points:
                if point == curr_point:
                    return id
                id += 1
        return -1

    def reset_ids(self):
        for i, group in enumerate(self.groups):
            group.id = i

    def get_idx(self, group):
        return self.groups.index(group)

    def remove_all(self):
        self.groups = []

    def set_this_as_first(self, point: KMPPoint):
        if self.get_index_from_point(point) == 0:
            return
        group_idx, group, point_idx = self.find_group_of_point(point)
        if point_idx == 0:
            self.groups.remove(group)
            self.groups.insert(0, group)
        else:
            self.split_group(group, group.points[point_idx - 1])
            new_group = self.groups.pop()
            self.groups.insert(0, new_group)

        self.merge_groups()


# Section 1
# Enemy/Item Route Code Start
class EnemyPoint(KMPPoint):
    def __init__(self,
                 position,
                 scale,
                 enemyaction,
                 enemyaction2,
                 unknown):
        super().__init__()
        self.position = position

        self.scale = scale
        self.enemyaction = enemyaction
        self.enemyaction2 = enemyaction2
        self.unknown = unknown

    @classmethod
    def new(cls):
        return cls(
            Vector3(0.0, 0.0, 0.0),
            10, 0, 0, 0
        )

    @classmethod
    def from_file(cls, f):
        point = cls.new()
        point.position = Vector3(*unpack(">fff", f.read(12)))
        point.scale = read_float(f)
        point.enemyaction = read_uint16(f)
        point.enemyaction2 = read_uint8(f)
        point.unknown = read_uint8(f)

        return point


    def write(self, f):

        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        f.write(pack(">f", self.scale ) )
        f.write(pack(">H", self.enemyaction) )
        f.write(pack(">bB", self.enemyaction2, self.unknown) )

class EnemyPointGroup(PointGroup):
    def __init__(self):
        super().__init__()

    @classmethod
    def new(cls):
        return cls()

    @classmethod
    def from_file(cls, f, idx, points):
        group = cls()
        group.id = idx
        start_idx = read_uint8(f)
        len = read_uint8(f)


        group.prevgroup = list(unpack(">bbbbbb", f.read(6)) )
        group.nextgroup = list(unpack(">bbbbbb", f.read(6)) )
        f.read( 2)

        for i in range(start_idx, start_idx + len):
            group.points.append(points[i])
            points[i].group = idx

        return group

    def copy_group(self):
        group = EnemyPointGroup()
        return super().copy_group( group)

    def copy_group_after(self, point, group):
        group = EnemyPointGroup()
        return super().copy_group_after(point, group)

    def write_points_enpt(self, f):
        for point in self.points:
            point.write(f)
        return len(self.points)

    def write_enph(self, f, index, groups):
        f.write(pack(">B", index) )
        f.write(pack(">B", len(self.points) ) )
        for grp in self.prevgroup:
           f.write(pack(">B", groups.get_idx(grp)))
        for i in range( 6 - len(self.prevgroup) ):
           f.write(pack(">b", -1))

        for grp in self.nextgroup:
           f.write(pack(">B", groups.get_idx(grp)))
        for i in range( 6 - len(self.nextgroup) ):
           f.write(pack(">b", -1))

        f.write(pack(">H",  0) )

class EnemyPointGroups(PointGroups):
    level_file = None
    def __init__(self):
        super().__init__()

    def get_new_point(self):
        return EnemyPoint.new()

    def get_new_group(self):
        return EnemyPointGroup.new()

    def remove_point(self, del_point):
        super().remove_point(del_point)

        type_4_areas : list[Area] = __class__.level_file.areas.get_type(4)
        for area in type_4_areas:
            if area.enemypoint == del_point:
                area.find_closest_enemypoint()

    def remove_group(self, del_group, merge = True):
        super().remove_group(del_group, merge = True)

        type_4_areas = __class__.level_file.areas.get_type(4)
        for area in type_4_areas:
            if area.enemypoint in del_group.points:
                area.enemypoint = None

    @classmethod
    def from_file(cls, f):
        enemypointgroups = cls()

        assert f.read(4) == b"ENPT"
        count = read_uint16(f)
        f.read(2)


        all_points = []
        #read the enemy points
        for i in range(count):
            enemypoint = EnemyPoint.from_file(f)
            all_points.append(enemypoint)

        assert f.read(4) == b"ENPH"
        count = read_uint16(f)
        f.read(2)


        for i in range(count):
            enemypath = EnemyPointGroup.from_file(f, i, all_points)
            enemypointgroups.groups.append(enemypath)

        return enemypointgroups

    def write(self, f):


        f.write(b"ENPT")
        count_offset = f.tell()
        f.write(pack(">H", 0) ) # will be overridden later
        f.write(pack(">H", 0) )

        sum_points = 0
        point_indices = []

        for group in self.groups:
            point_indices.append(sum_points)
            sum_points += group.write_points_enpt(f)
        enph_offset = f.tell()

        if sum_points > 0xFF:
            raise Exception("too many enemy points")
        else:
            f.seek(count_offset)
            f.write(pack(">H", sum_points) )

        f.seek(enph_offset)
        f.write(b"ENPH")
        f.write(pack(">H", len(self.groups) ) )
        f.write(pack(">H", 0) )

        for idx, group in enumerate( self.groups ):
            group.write_enph(f, point_indices[idx], self)

        return enph_offset

class ItemPoint(KMPPoint):
    def __init__(self, position, scale, setting1, setting2) :
        super().__init__()
        self.position = position
        self.scale = scale
        self.setting1 = setting1

        self.unknown = setting2 & 0x4
        self.lowpriority = setting2 & 0x2
        self.dontdrop = setting2 & 0x1

    @classmethod
    def new(cls):
        return cls( Vector3(0.0, 0.0, 0.0), 0, 1, 0)

    def set_setting2(self, setting2):
        self.unknown = setting2 & 0x4
        self.lowpriority = setting2 & 0x2
        self.dontdrop = setting2 & 0x1

    @classmethod
    def from_file(cls, f):

        point = cls.new()

        point.position = Vector3(*unpack(">fff", f.read(12)))
        point.scale = read_float(f)
        point.setting1 = read_uint16(f)
        point.set_setting2(read_uint16(f))

        return point


    def write(self, f):

        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))

        setting2 = self.unknown << 0x2
        setting2 = setting2 | (self.lowpriority << 0x1)
        setting2 = setting2 | self.dontdrop
        f.write(pack(">fHH", self.scale, self.setting1, setting2))

class ItemPointGroup(PointGroup):
    def __init__(self):
        super().__init__()

    @classmethod
    def new(cls):
        return cls()

    @classmethod
    def from_file(cls, f, idx, points):
        group = cls()
        group.id = idx
        start_idx = read_uint8(f)
        len = read_uint8(f)


        group.prevgroup = list( unpack(">bbbbbb", f.read(6)) )
        group.nextgroup = list(unpack(">bbbbbb", f.read(6)) )
        f.read( 2)

        for i in range(start_idx, start_idx + len):
            group.points.append(points[i])
            points[i].group = idx

        return group

    def copy_group(self):
        group = ItemPointGroup()
        return super().copy_group(group)

    def copy_group_after(self, point, group):
        group = ItemPointGroup()
        return super().copy_group_after( point, group)

    def write_itpt(self, f):
        for point in self.points:
            point.write(f)
        return len(self.points)

    def write_itph(self, f, index, groups):


        f.write(pack(">B", index ) )
        f.write(pack(">B", len(self.points) ) )

        for grp in self.prevgroup:
           f.write(pack(">B", groups.get_idx(grp)))
        for i in range( 6 - len(self.prevgroup) ):
           f.write(pack(">b", -1))
        for grp in self.nextgroup:
           f.write(pack(">B", groups.get_idx(grp)))
        for i in range( 6 - len(self.nextgroup) ):
           f.write(pack(">b", -1))

        f.write(pack(">H",  0) )

class ItemPointGroups(PointGroups):
    def __init__(self):
        super().__init__()

    def get_new_point(self):
        return ItemPoint.new()

    def get_new_group(self):
        return ItemPointGroup.new()


    @classmethod
    def from_file(cls, f):
        itempointgroups = cls()

        assert f.read(4) == b"ITPT"
        count = read_uint16(f)
        f.read(2)


        all_points = []
        #read the item points
        for i in range(count):
            itempoint = ItemPoint.from_file(f)
            all_points.append(itempoint)


        assert f.read(4) == b"ITPH"
        count = read_uint16(f)
        f.read(2)


        for i in range(count):
            itempath = ItemPointGroup.from_file(f, i, all_points)
            itempointgroups.groups.append(itempath)
        return itempointgroups

    def write(self, f):

        f.write(b"ITPT")

        count_offset = f.tell()
        f.write(pack(">H", 0) ) #overwritten
        f.write(pack(">H", 0) )

        sum_points = 0
        point_indices = []

        for group in self.groups:
            point_indices.append(sum_points)
            sum_points += group.write_itpt(f)

        itph_offset = f.tell()

        if sum_points > 0xFF:
            raise Exception("too many enemy points")
        else:
            f.seek(count_offset)
            f.write(pack(">H", sum_points) )

        f.seek(itph_offset)

        f.write(b"ITPH")
        f.write(pack(">H", len(self.groups) ) )
        f.write(pack(">H", 0) )

        for idx, group in enumerate( self.groups ):
            group.write_itph(f, point_indices[idx], self)


        return  itph_offset

class Checkpoint(KMPPoint):
    def __init__(self, start, end, respawn=0, type=0):
        self.start = start
        self.end = end
        self.mid = (start+end)/2.0
        self.respawnid = respawn
        self.respawn_obj = None
        self.type = type
        self.lapcounter = 0


        self.prev = -1
        self.next = -1

        self.widget = None

    @classmethod
    def new(cls):
        return cls(Vector3(0.0, 0.0, 0.0),
                   Vector3(0.0, 0.0, 0.0))

    def assign_to_closest(self, respawns):
        mid = (self.start + self.end) / 2
        distances = [ respawn.position.distance_2d( mid  ) for respawn in respawns ]
        if len(distances) > 0:
            smallest = [ i for i, x in enumerate(distances) if x == min(distances)]
            self.respawn_obj = respawns[smallest[0]]

    def get_mid(self):
        return (self.start+self.end)/2.0

    @classmethod
    def from_file(cls, f):
        checkpoint = cls.new()

        checkpoint.start = Vector3(*unpack(">f", f.read(4) ), 0, *unpack(">f", f.read(4) ) )
        checkpoint.end = Vector3(*unpack(">f", f.read(4) ), 0, *unpack(">f", f.read(4) ) )

        checkpoint.respawnid = read_uint8(f) #respawn

        checkpoint_type = read_uint8(f)
        if checkpoint_type == 0:
            checkpoint.lapcounter = 1
        elif checkpoint_type != 0xFF:
            checkpoint.type = 1

        checkpoint.prev = read_uint8(f)
        checkpoint.next = read_uint8(f)

        return checkpoint


    def write(self, f, prev, next, key, lap_counter = False ):
        f.write(pack(">ff", self.start.x, self.start.z))
        f.write(pack(">ff", self.end.x, self.end.z))
        f.write(pack(">b", self.respawnid))

        if self.lapcounter == 1:
            f.write(pack(">b", 0))
            key = 1
        elif self.type == 1:
            f.write(pack(">b", key))
            key += 1
        else:
            f.write(pack(">B", 0xFF))
        f.write(pack(">BB", prev & 0xFF, next & 0xFF) )
        return key

class CheckpointGroup(PointGroup):
    def __init__(self):
        super().__init__()

    @classmethod
    def new(cls):
        return cls()

    def copy_group(self):
        group = CheckpointGroup()
        return super().copy_group( group)


    def copy_group_after(self, point, group):
        group = CheckpointGroup()
        return super().copy_group_after( point, group)

    def get_used_respawns(self):
        return set( [checkpoint.respawn_obj for checkpoint in self.points]  )

    def num_key_cps(self):
        return sum( [1 for ckpt in self.points if ckpt.type > 0]  )

    @classmethod
    def from_file(cls, f, all_points, id):

        checkpointgroup = cls.new()
        checkpointgroup.id = id

        start_point = read_uint8(f)
        length = read_uint8(f)

        if len(all_points) > 0:
            assert( all_points[start_point].prev == 0xFF )
            if length > 1:
                assert( all_points[start_point + length - 1].next == 0xFF)
        checkpointgroup.points = all_points[start_point: start_point + length]

        checkpointgroup.prevgroup = list(unpack(">bbbbbb", f.read(6)))
        checkpointgroup.nextgroup = list(unpack(">bbbbbb", f.read(6)))
        f.read(2)

        return checkpointgroup

    def set_rspid(self, rsps):
        for point in self.points:
            if point.respawn_obj is not None:
                point.respawnid = rsps.index(point.respawn_obj)
            else:
                point.respawnid = -1

    def write_ckpt(self, f, key, prev):

        if len(self.points) > 0:
            key = self.points[0].write(f, -1, 1 + prev, key)

            for i in range(1, len( self.points) -1 ):
                key = self.points[i].write(f, i-1 + prev, i + 1 + prev, key)
            if len(self.points) > 1:
                key = self.points[-1].write(f, len(self.points) - 2 + prev, -1, key)
        return key

    def write_ckph(self, f, index, groups):
        #print(index, len(self.points), self.prevgroup, self.nextgroup)
        f.write(pack(">B", index ) )
        f.write(pack(">B", len(self.points) ) )

        for grp in self.prevgroup:
           f.write(pack(">B", groups.get_idx(grp)))
        for i in range( 6 - len(self.prevgroup) ):
           f.write(pack(">b", -1))
        for grp in self.nextgroup:
           f.write(pack(">B", groups.get_idx(grp)))
        for i in range( 6 - len(self.nextgroup) ):
           f.write(pack(">b", -1))

        f.write(pack(">H",  0) )

class CheckpointGroups(PointGroups):
    def __init__(self):
        super().__init__()

    def get_new_point(self):
        return Checkpoint.new()

    def get_new_group(self):
        return CheckpointGroup.new()

    @classmethod
    def from_file(cls, f, ckph_offset):
        checkpointgroups = cls()
        #print("ckpt offset", hex(f.tell()))
        assert f.read(4) == b"CKPT"
        count = read_uint16(f)
        f.read(2)

        #print(count)

        all_points = []
        #read the enemy points
        for i in range(count):
            checkpoint = Checkpoint.from_file(f)
            all_points.append(checkpoint)

        #print("ckph offset", hex(f.tell()))
        assert f.read(4) == b"CKPH"
        count = read_uint16(f)
        f.read(2)

        for i in range(count):
            checkpointpath = CheckpointGroup.from_file(f, all_points, i)
            checkpointgroups.groups.append(checkpointpath)

        return checkpointgroups

    def write(self, f):
        f.write(b"CKPT")
        tot_points = self.num_total_points()
        if tot_points > 255:
            raise Exception("too many checkpoints")
        f.write(pack(">H", tot_points ) )
        f.write(pack(">H", 0) )

        sum_points = 0
        indices_offset = []
        num_key = 0
        starting_key_cp = [0] * len(self.groups)

        if len(self.groups) > 0:
            starting_key_cp[0] = 0

        for i, group in enumerate(self.groups):
            indices_offset.append(sum_points)
            num_key = group.write_ckpt(f, starting_key_cp[i], sum_points)

            for grp in group.nextgroup:
                id = self.get_idx(grp)
                starting_key_cp[ id ] = max( starting_key_cp[id], num_key)

            sum_points += len(group.points)
        ckph_offset = f.tell()

        f.write(b"CKPH")
        f.write(pack(">H", len(self.groups) ) )
        f.write(pack(">H", 0) )

        for idx, group in enumerate( self.groups ):
            group.write_ckph(f, indices_offset[idx], self)
        return ckph_offset

    def set_key_cps(self):
        #assume that checkpoint 0 is always the first one
        to_visit = [0]
        splits = [0]
        visited = []

        while len(to_visit) > 0:
            i = to_visit.pop(0)

            if i in visited:
                continue
            visited.append(i)
            checkgroup = self.groups[i]

            if len(splits) == 1:
                checkgroup.points[0].type = 1

                for i in range(10, len(checkgroup.points), 10):
                    checkgroup.points[i].type = 1

                checkgroup.points[-1].type = 1

            actual_next = [x for x in checkgroup.nextgroup if x != -1]

            splits.extend(actual_next)
            splits = [*set(splits)]
            splits = [x for x in splits if x != i]

            to_visit.extend(actual_next)
            to_visit = [*set(to_visit)]

    def get_used_respawns(self):
        used_respawns = []
        for group in self.groups:
            used_respawns.extend( group.get_used_respawns() )

        return set(used_respawns)

    def set_rspid(self, rsps):
        for group in self.groups:
            group.set_rspid(rsps)


# Section 3
# Routes/Paths for cameras, objects and other things
class Route(object):
    def __init__(self):
        self.points = []
        self._pointcount = 0
        self._pointstart = 0
        self.smooth = 0
        self.cyclic = 0

        self.used_by = []

    @classmethod
    def new(cls, obj = None):
        route = cls ()
        if obj is not None:
            point1 = RoutePoint.new()
            point1.position = obj.position
            route.points.append(point1)

            point2 = RoutePoint.new()
            point2.position = obj.position + Vector3(500, 0, 0)
            route.points.append(point2)

            route.used_by.append(obj)
        return route

    def copy(self):
        this_class = self.__class__
        obj = this_class.new()
        return self.copy_params_to_child(obj)

    def to_object(self):
        object_route = ObjectRoute()
        self.copy_params_to_child(object_route, False)
        return object_route

    def to_camera(self):
        camera_route = CameraRoute()
        self.copy_params_to_child(camera_route, False)
        return camera_route

    def to_area(self):
        area_route = AreaRoute()
        self.copy_params_to_child(area_route, False)
        return area_route

    def copy_params_to_child(self, new_route, deep_copy = True):
        if deep_copy:
            for point in self.points:
                new_point = point.copy()
                new_point.partof = new_route
                new_route.points.append(new_point)
        else:
            new_route.points = self.points
        new_route.smooth = self.smooth
        new_route.cyclic = self.cyclic
        if deep_copy:
            new_route.used_by = []
        else:
            new_route.used_by = self.used_by

        return new_route

    def total_distance(self):
        distance = 0
        for i, point in enumerate(self.points[:-1]):
            distance += point.position.distance( self.points[i + 1].position  )
        return distance

    @classmethod
    def from_file(cls, f):
        route = cls()
        route._pointcount = read_uint16(f)
        route.smooth = read_uint8(f)
        route.cyclic = read_uint8(f)


        for i in range(route._pointcount):
            route.points.append( RoutePoint.from_file(f, route)  )

        return route


    def add_routepoints(self, points):
        for i in range(self._pointcount):
            self.points.append(points[self._pointstart+i])



    def write(self, f):
         f.write(pack(">H", len(self.points) ) )


         f.write(pack(">B", self.smooth & 0xFF ) )

         f.write(pack(">B", self.cyclic) )

         for point in self.points[0:-1]:
            point.write(f)
         if len(self.points) > 0:
            self.points[-1].write(f, True)
         return len(self.points)

#here for type checking - they function in the same way
class ObjectRoute(Route):
    def __init__(self):
        super().__init__()
        self.type = 0

class CameraRoute(Route):
    def __init__(self):
        super().__init__()
        self.type = 1


class AreaRoute(Route):
    def __init__(self):
        super().__init__()
        self.type = 2

    @classmethod
    def new(cls):
        return cls()

# Section 4
# Route point for use with routes from section 3
class RoutePoint(object):
    def __init__(self, position):
        self.position = position
        self.unk1 = 0
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
    def from_file(cls, f, partof = None):
        position = Vector3(*unpack(">fff", f.read(12)))
        point = cls(position)

        point.unk1 = read_uint16(f)
        point.unk2 = read_uint16(f)
        point.partof = partof
        return point


    def copy(self):
        obj = self.__class__.new()
        obj.position = Vector3(self.position.x, self.position.y, self.position.z)
        obj.partof = self.partof
        obj.unk1 = self.unk1
        obj.unk2 = self.unk2
        return obj



    def write(self, f, force_actual = False):
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z ) )
        f.write(pack(">HH", self.unk1, self.unk2) )

# Section 5
# Objects
class MapObject(object):
    level_file = None
    can_copy = True

    def __init__(self, position, objectid):
        self.objectid = objectid
        self.position = position
        self.rotation = Rotation.default()
        self.scale = Vector3(1.0, 1.0, 1.0)

        self.route = -1
        self.route_obj = None
        self.userdata = [0 for i in range(8)]

        self.single = 1
        self.double = 1
        self.triple = 1

        self.widget = None
        self.route_info = None

    @classmethod
    def get_empty(cls):
        null_obj = cls.new()
        null_obj.objectid = None
        null_obj.position = None
        null_obj.rotation = None
        null_obj.scale = None
        null_obj.route_obj = None
        null_obj.userdata = [None] * 8
        null_obj.single = 0
        null_obj.double = 0
        null_obj.triple = 0

    @classmethod
    def new(cls, obj_id = 101):
        return cls(Vector3(0.0, 0.0, 0.0), obj_id)

    @classmethod
    def default_item_box(cls):
        item_box = cls(Vector3(0.0, 0.0, 0.0), 101)
        return item_box

    def split_prescence(self, prescence):
        self.single = prescence & 0x1
        self.double = prescence & 0x2 >> 1
        self.triple = prescence & 0x4 >> 2

    @classmethod
    def all_of_same_id(cls, objs):
        return all([obj.objectid == objs[0].objectid for obj in objs])

    @classmethod
    def common_obj(cls, objs):
        cmn = objs[0].copy()
        members = [attr for attr in dir(cmn) if not callable(getattr(cmn, attr)) and not attr.startswith("__")]
        print(members)
        return cmn


    @classmethod
    def from_file(cls, f):
        object = cls.new()

        object.objectid = read_uint16(f)


        f.read(2)
        object.position = Vector3(*unpack(">fff", f.read(12)))
        object.rotation = Rotation.from_file(f)

        object.scale = Vector3(*unpack(">fff", f.read(12)))
        object.route = read_uint16(f)
        if object.route == 65535:
            object.route = -1
        object.userdata = list(unpack(">hhhhhhhh", f.read(2 * 8)))
        object.split_prescence( read_uint16(f) )

        return object

    def write(self, f, route_start):

        f.write(pack(">H", self.objectid  ))


        f.write(pack(">H", 0) )
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        self.rotation.write(f)
        f.write(pack(">fff", self.scale.x, self.scale.y, self.scale.z))
        route = self.set_route()
        route = (2 ** 16 - 1) if route == -1 else route + route_start
        f.write(pack(">H", route) )

        for i in range(8):
            f.write(pack(">h", self.userdata[i]))

        presence = self.single | (self.double << 1) | (self.triple << 2)

        f.write( pack(">H", presence) )
        return 1
    def copy(self):

        route_obj = self.route_obj
        widget = self.widget
        self.route_obj = None
        self.widget = None

        new_object = deepcopy(self)

        self.route_obj = route_obj
        self.widget = widget

        new_object.route_obj = route_obj

        return new_object

    def has_route(self):
         from widgets.data_editor import load_route_info

         if self.objectid in OBJECTNAMES:
            name = OBJECTNAMES[self.objectid]
            route_info = load_route_info(name)
            self.route_info = route_info

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

    def set_route(self):
        for i, route in enumerate(__class__.level_file.routes):
            if route == self.route_obj:
                return i
        return -1

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
            if obj is not None:
                mapobjs.objects.append(obj)

        return mapobjs

    def write(self, f, start_route = 0):

        f.write(b"GOBJ")
        f.write(pack(">H", len(self.objects)))
        f.write(pack(">H", 0) )

        #print(bol2kmp)
        for object in self.objects:
            object.write(f, start_route)

    def get_routes(self):
        return list(set([obj.route_obj for obj in self.objects if obj.route_obj is not None and obj.has_route()]))

# Section 6
# Kart/Starting positions

class KartStartPoint(object):
    def __init__(self, position):
        self.position = position
        self.rotation = Rotation.default()
        self.playerid = 0xFF

    @classmethod
    def new(cls):
        return cls(Vector3(0.0, 0.0, 0.0))

    @classmethod
    def from_file(cls, f):
        position = Vector3(*unpack(">fff", f.read(12)))

        kstart = cls(position)
        kstart.rotation = Rotation.from_file(f, True)
        kstart.playerid = read_uint8(f)
        return kstart

    def write(self,f):
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))

        self.rotation.write(f)

        if self.playerid == 0xFF:
            f.write(pack(">H", self.playerid + 0xFF00 ) )
        else:
            f.write(pack(">H", self.playerid ) )
        f.write(pack(">H",  0) )

class KartStartPoints(object):
    def __init__(self):
        self.positions = []

        self.pole_position = 0
        self.start_squeeze = 0

        self.widget = None


    @classmethod
    def from_file(cls, f, count):
        kspoints = cls()
        for i in range(count):
            kstart = KartStartPoint.from_file(f)
            kspoints.positions.append(kstart)

        return kspoints

    def write(self, f):
        f.write(b"KTPT")
        f.write(pack(">H", len(self.positions)))
        f.write(pack(">H", 0) )
        for position in self.positions:
            position.write(f)

# Section 7
# Areas
class Area(object):
    level_file = None
    can_copy = True
    def __init__(self, position):
        self.shape = 0
        self.type = 0
        self.cameraid = -1
        self.camera = None
        self.priority = 0

        self.position = position
        self.rotation = Rotation.default()
        self.scale = Vector3(1.0, 1.0, 1.0)

        self.setting1 = 0
        self.setting2 = 0

        self.route = -1
        self.route_obj = None

        self.enemypointid = -1
        self.enemypoint = None

        self.widget = None

    @classmethod
    def new(cls):
        return cls(Vector3(0.0, 0.0, 0.0))

    @classmethod
    def default(cls, type = 0):
        area = cls(Vector3(0.0, 0.0, 0.0))
        area.scale = Vector3(1, .5, 1)
        area.type = type
        return area

    @classmethod
    def from_file(cls, f):

        shape = read_uint8(f) #shape
        type = read_uint8(f)
        camera = read_int8(f)
        priority = read_uint8(f)    #priority

        position = Vector3(*unpack(">fff", f.read(12)))
        area = cls(position)

        area.shape = shape
        area.type = type

        area.cameraid = camera
        if type != 0:
            area.cameraid = -1
        area.priority = priority
        area.rotation = Rotation.from_file(f)

        area.scale = Vector3(*unpack(">fff", f.read(12)))

        area.setting1 = read_int16(f) #unk1
        area.setting2 = read_int16(f) #unk2
        area.route = read_uint8(f) #route
        if area.type != 3:
            area.route = -1
        area.enemypointid = read_uint8(f) #enemy
        if area.type != 4:
            area.enemypointid = -1

        f.read(2)

        return area

    def write(self, f, start_route = 0):
        f.write(pack(">B", self.shape) ) #shape
        f.write(pack(">B", self.type ) )
        cameraid = self.set_camera()
        cameraid = 255 if cameraid < 0 else cameraid
        f.write(pack(">B", cameraid) )
        f.write(pack(">B", self.priority) ) #priority

        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        self.rotation.write(f)
        f.write(pack(">fff", self.scale.x, self.scale.y, self.scale.z))

        enemypointid = self.set_enemypointid()
        enemypointid = 255 if enemypointid < 0 else enemypointid
        route = self.set_route()
        route = 255 if route < 0 else route + start_route
        f.write(pack(">HHBBH", self.setting1, self.setting2, route, enemypointid, 0 ) )
        return 1

    def copy(self):
        enemypoint = self.enemypoint
        camera = self.camera
        route_obj = self.route_obj
        widget = self.widget

        self.enemypoint = None
        self.camera = None
        self.route_obj = None
        self.widget = None

        new_area = deepcopy(self)

        self.enemypoint = enemypoint
        self.camera = camera
        self.route_obj = route_obj
        self.widget = widget

        new_area.enemypoint = enemypoint
        new_area.camera = camera
        new_area.route_obj = route_obj

        return new_area

    #type 0 - camera
    def set_camera(self):
        if self.type == 0:
            for i, camera in enumerate(__class__.level_file.replaycameras):
                if camera == self.camera:
                    return i
        return -1

    #type 3 - moving road
    def set_route(self):
        if self.type == 3:
            for i, route in enumerate(__class__.level_file.arearoutes):
                if route == self.route_obj:
                    return i
        return -1

    #type 4 - force recalc
    def set_enemypointid(self):
        if self.type == 4:
            point_idx = __class__.level_file.enemypointgroups.get_index_from_point(self.enemypoint)
            return point_idx
        return -1

    def find_closest_enemypoint(self):
        enemygroups = __class__.level_file.enemypointgroups.groups
        min_distance = 9999999999999
        self.enemypoint = None
        for group in enemygroups:
            for point in group.points:
                distance = self.position.distance( point.position)
                if distance < min_distance:
                    self.enemypoint = point
                    min_distance = distance

    def remove_self(self):
        if self.camera is not None:
            self.camera.used_by.remove(self)
            if len(self.camera.used_by) == 0:
                #delete the camera
                self.__class__.level_file.remove_camera(self.camera)

        if self.route_obj is not None:
            self.route_obj.used_by.remove(self)
            if len(self.route_obj.used_by) == 0:
                self.__class__.level_file.arearoutes.remove(self.route_obj)

class Areas(ObjectContainer):
    def __init__(self):
        super().__init__()

    @classmethod
    def from_file(cls, f, count):
        areas = cls()
        for i in range(count):
            new_area = Area.from_file(f)
            if new_area is not None:
                areas.append(new_area)

        return areas

    def write(self, f, start_route = 0):
        f.write(b"AREA")
        area_count_off = f.tell()
        f.write(pack(">H", 0xFFFF) )
        f.write(pack(">H", 0) )

        num_written = 0
        for area in self:
            num_written += area.write(f, start_route)

        end_sec = f.tell()
        f.seek(area_count_off)
        f.write(pack(">H", num_written) )
        f.seek(end_sec)

    def get_type(self, area_type):
        return [area for area in self if area.type == area_type]

    def remove_area(self, area : Area):
        area.remove_self()
        self.remove(area)

    def remove_invalid(self):
        invalid_areas = [area for area in self if area.type < 0 or area.type > 10]
        for area in invalid_areas:
            self.remove_area( area )

    def get_cameras(self):
        return [area.camera for area in self]

class ReplayAreas(Areas):
    def __init__(self):
        super().__init__()

    def get_cameras(self):
        return [area.camera for area in self]

    def get_routes(self):
        cameras = self.get_cameras()
        return list(set([cam.route_obj for cam in cameras if cam.route_obj is not None and cam.has_route()]))
# Section 8
# Cameras
class FOV:
    def __ini__(self):
        self.start = 0
        self.end = 0
class Cameras(ObjectContainer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.startcamid = -1
        self.startcam = None

    @classmethod
    def from_file(cls, f, count):
        cameras = cls()
        for i in range(count):

            cameras.append( Camera.from_file(f) )

        return cameras

    def add_goal_camera(self):
        came_types_exist = [ camera.type for camera in self]
        if 0 not in came_types_exist:
            self.append(  Camera.new_type_0() )

    def to_opening(self):
        for camera in self:
            camera.__class__ = OpeningCamera

    def to_replay(self):
       for camera in self:
            camera.__class__ = ReplayCamera

    def get_type(self, type):
        return [cam for cam in self if cam.type == type]

    def get_routes(self):
        return list(set([cam.route_obj for cam in self if cam.route_obj is not None and cam.has_route()]))

class Camera(object):
    level_file = None
    can_copy = True
    def __init__(self, position):
        self.type = 0
        self.nextcam = -1
        self.nextcam_obj = None
        self.shake = 0
        self.route = -1
        self.route_obj = None
        self.routespeed = 0
        self.zoomspeed = 0
        self.viewspeed = 0
        self.startflag = 0
        self.movieflag = 0

        self.position = position
        self.rotation = Rotation.default()



        self.fov = FOV()

        self.position2 = Vector3(0.0, 0.0, 0.0)
        self.position3 = Vector3(0.0, 0.0, 0.0)


        self.camduration = 0

        self.widget = None
        self.used_by = []

    @classmethod
    def new(cls):
        return cls(Vector3(0.0, 0.0, 0.0))
    @classmethod
    def default(cls, type = 2):
        camera = cls(Vector3(0.0, 0.0, 0.0))
        camera.type = type
        camera.fov.start = 30
        camera.fov.end = 50

        return camera

    @classmethod
    def from_file(cls, f):

        type = read_uint8(f)

        type = min(type, 10)

        next_cam = read_int8(f)
        shake = read_uint8(f)
        route = read_int8(f)

        move_velocity = read_uint16(f)
        zoom_velocity = read_uint16(f)
        view_velocity = read_uint16(f)

        start_flag = read_uint8(f)
        movie_flag = read_uint8(f)

        position = Vector3(*unpack(">fff", f.read(12)))
        cam = cls(position)

        cam.type = type
        cam.nextcam = next_cam
        cam.shake = shake
        cam.route = route
        cam.routespeed = move_velocity
        cam.zoomspeed = zoom_velocity
        cam.viewspeed = view_velocity

        cam.startflag = start_flag
        cam.movieflag = movie_flag


        #print(rotation)
        cam.rotation = Rotation.from_file(f)

        cam.fov.start = read_float(f)
        cam.fov.end = read_float(f)
        cam.position2 = Vector3(*unpack(">fff", f.read(12)))
        cam.position3 = Vector3(*unpack(">fff", f.read(12)))
        cam.camduration = read_float(f)

        return cam

    def copy(self):
        nextcam_obj = self.nextcam_obj
        route_obj = self.route_obj
        widget = self.widget
        used_by = self.used_by



        new_camera = self.__class__.new()
        new_camera.position = Vector3(self.position.x, self.position.y, self.position.z)
        new_camera.position2 = Vector3(self.position2.x, self.position2.y, self.position2.z)
        new_camera.position3 = Vector3(self.position3.x, self.position3.y, self.position3.z)
        new_camera.rotation = self.rotation.copy()

        new_camera.type = self.type
        new_camera.nextcam_obj = self.nextcam_obj
        new_camera.shake = self.shake
        new_camera.route_obj = self.route_obj
        new_camera.routespeed = self.routespeed
        new_camera.zoomspeed = self.zoomspeed
        new_camera.viewspeed = self.viewspeed

        new_camera.startflag = self.startflag
        new_camera.movieflag = self.movieflag

        new_camera.fov.start = self.fov.start
        new_camera.fov.end = self.fov.end

        new_camera.camduration = self.camduration


        return new_camera

    def write(self, f, route_start = 0, cam_start = 0, camroutes = None):

        f.write(pack(">B", self.type ) )
        nextcam = self.set_nextcam()
        nextcam = 255 if nextcam < 0 else nextcam + cam_start
        route = self.set_route(camroutes)
        route = 255 if route < 0 else route + route_start
        f.write(pack(">BBB", nextcam, 0, route) )

        f.write(pack(">H", self.routespeed ) )
        f.write(pack(">H", self.zoomspeed ) )
        f.write(pack(">H", self.viewspeed ) )

        f.write(pack(">B", self.startflag ) )
        f.write(pack(">B", self.movieflag ) )


        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        self.rotation.write(f)

        f.write(pack(">ff", self.fov.start, self.fov.end))

        f.write(pack(">fff", self.position2.x, self.position2.y, self.position2.z))
        f.write(pack(">fff", self.position3.x, self.position3.y, self.position3.z))
        f.write(pack(">f", self.camduration) )

        return 1

    @classmethod
    def new_type_0(cls):
        cam =  cls(Vector3(-860.444, 6545.688, 3131.74))
        cam.position2 = Vector3(-30, -1.0, 550)
        cam.position3 = Vector3(-5, 1.0, 0)
        cam.zoomspeed = 30
        cam.fov.start = 85
        cam.fov.end = 40

        return cam

    def has_route(self):
        return (self.type in [2, 5, 6])

    def set_route(self, routes):
        if self.has_route():
            for i,route in enumerate(routes):
                if route == self.route_obj:
                    return i
        return -1

    def set_nextcam(self):
        if self.nextcam_obj is None:
            return -1
        for i, camera in enumerate(__class__.level_file.cameras):
            if self.nextcam_obj == camera:
                return i
        return -1

    def handle_route_change(self):
        if self.has_route() and self.route_obj is None:
            self.route_obj = CameraRoute.new(self)


class ReplayCamera(Camera):
    @classmethod
    def from_generic(cls, generic):
        generic.__class__ = cls
        return generic


class OpeningCamera(Camera):

    @classmethod
    def from_generic(cls, generic):
        generic.__class__ = cls
        return generic

# Section 9
# Jugem Points
class JugemPoint(object):
    def __init__(self, position):
        self.position = position
        self.rotation = Rotation.default()
        #self.respawn_id = 0
        self.range = 0


    @classmethod
    def new(cls):
        return cls(Vector3(0.0, 0.0, 0.0))


    @classmethod
    def from_file(cls, f):
        position = Vector3(*unpack(">fff", f.read(12)))
        jugem = cls(position)

        #rotation = Vector3(*unpack(">fff", f.read(12)))
        #print(rotation)
        jugem.rotation = Rotation.from_file(f)


        #jugem.respawn_id = read_uint16(f)
        read_uint16(f)

        jugem.range = read_int16(f)

        return jugem


    def write(self, f, count):
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        self.rotation.write(f)
        f.write(pack(">H", count) )
        f.write(pack(">h", self.range ) )

class CannonPoint(object):
    def __init__(self, position):
        self.position = position
        self.rotation = Rotation.default()
        self.id = 0
        self.shoot_effect = 0


    @classmethod
    def new(cls):
        return cls(Vector3(0.0, 0.0, 0.0))

    @classmethod
    def from_file(cls, f):
        position = Vector3(*unpack(">fff", f.read(12)))
        cannon = cls(position)

        cannon.rotation = Rotation.from_file(f)
        cannon.id = read_uint16(f)
        cannon.shoot_effect = read_int16(f)

        return cannon


    def write(self, f):
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        self.rotation.write(f)
        f.write(pack(">Hh", self.id, self.shoot_effect) )

class MissionPoint(object):
    def __init__(self, position):
        self.position = position
        self.rotation = Rotation.default()
        self.mission_id = 0
        self.unk = 0


    @classmethod
    def new(cls):
        return cls(Vector3(0.0, 0.0, 0.0))

    @classmethod
    def from_file(cls, f):
        position = Vector3(*unpack(">fff", f.read(12)))
        jugem = cls(position)

        jugem.rotation = Rotation.from_file(f)
        jugem.mission_id = read_uint16(f)
        jugem.unk = read_uint16(f)

        return jugem


    def write(self, f, count):
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        self.rotation.write(f)
        f.write(pack(">HH", count, self.unk) )

class KMP(object):
    def __init__(self):
        self.lap_count = 3
        self.pole_position = 0
        self.start_squeeze = 0
        self.lens_flare = 1
        self.flare_color = ColorRGB(255, 255, 255)
        self.flare_alpha = 0x32
        self.speed_modifier = 0

        self.kartpoints = KartStartPoints()
        self.enemypointgroups = EnemyPointGroups()
        self.itempointgroups = ItemPointGroups()

        self.checkpoints = CheckpointGroups()
        self.routes = ObjectContainer()

        self.objects = MapObjects()

        self.areas = Areas()
        self.arearoutes = ObjectContainer()

        self.replayareas = ReplayAreas()
        self.replaycameras = Cameras()

        self.cameras = Cameras()

        self.cameraroutes = ObjectContainer()
        self.replaycameraroutes = ObjectContainer()

        self.respawnpoints = ObjectContainer()
        self.cannonpoints = ObjectContainer()

        self.missionpoints = ObjectContainer()

        Area.level_file = self
        Camera.level_file = self
        MapObject.level_file = self
        EnemyPointGroups.level_file = self

        self.set_assoc()

    def set_assoc(self):
        self.routes.assoc = ObjectRoute
        self.cameraroutes.assoc = CameraRoute
        self.arearoutes.assoc = AreaRoute
        self.respawnpoints.assoc = JugemPoint
        self.cannonpoints.assoc = CannonPoint
        self.missionpoints.assoc = MissionPoint

    @classmethod
    def make_useful(cls):
        kmp = cls()

        first_enemy = EnemyPointGroup.new()
        kmp.enemypointgroups.groups.append(first_enemy)
        first_enemy.add_new_prev(first_enemy)
        first_enemy.add_new_next(first_enemy)

        first_item = ItemPointGroup.new()
        kmp.itempointgroups.groups.append(first_item)
        first_item.add_new_prev(first_item)
        first_item.add_new_next(first_item)

        first_checkgroup = CheckpointGroup.new()
        kmp.checkpoints.groups.append(first_checkgroup)
        first_checkgroup.add_new_prev(first_checkgroup)
        first_checkgroup.add_new_next(first_checkgroup)
        kmp.kartpoints.positions.append( KartStartPoint.new() )

        kmp.respawnpoints.append(JugemPoint.new())

        kmp.cameras.add_goal_camera()

        return kmp

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
        for route in self.arearoutes:
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

        for area in self.areas:
            assert area is not None
            yield area

        for area in self.replayareas:
            assert area is not None
            yield area

        for camera in self.cameras:
            assert camera is not None
            yield camera

        for camera in self.cameras:
            assert camera is not None
            yield camera

        for respawnid in self.respawnpoints:
            assert respawnid is not None
            yield respawn

        for cannon in self.cannonpoints:
            assert cannon is not None
            yield cannon

        for mission in self.missionpoints:
            assert mission is not None
            yield mission

    def get_all_objects(self):
        objects = []

        for group in self.enemypointgroups.groups:
            objects.append(group)
            objects.extend(group.points)

        for group in self.itempointgroups.groups:
            objects.append(group)
            objects.extend(group.points)

        for group in self.checkpoints.groups:
            objects.append(group)
            objects.extend(group.points)

        for route in self.routes:
            objects.append(route)
            objects.extend(route.points)

        for route in self.cameraroutes:
            objects.append(route)
            objects.extend(route.points)

        objects.extend(self.objects.objects)
        objects.extend(self.kartpoints.positions)
        objects.extend(self.areas)
        objects.extend(self.replayareas)
        objects.extend(self.cameras)
        objects.extend(self.replaycameras)
        objects.extend(self.respawnpoints)
        objects.extend(self.cannonpoints)
        objects.extend(self.missionpoints)

        return objects

    @classmethod
    def from_file(cls, f):
        kmp = cls()
        magic = f.read(4)
        assert magic == b"RKMD"


        f.read(0xC)       #header stuff
        ktpt_offset = read_uint32(f)
        enpt_offset = read_uint32(f)
        enph_offset = read_uint32(f)
        itpt_offset = read_uint32(f)
        itph_offset = read_uint32(f)
        ckpt_offset = read_uint32(f)
        ckph_offset = read_uint32(f)
        gobj_offset = read_uint32(f)
        poti_offset = read_uint32(f)
        area_offset = read_uint32(f)
        came_offset = read_uint32(f)
        jgpt_offset = read_uint32(f)
        cnpt_offset = read_uint32(f)
        mspt_offset = read_uint32(f)
        stgi_offset = read_uint32(f)

        header_len = f.tell()
        f.seek(ktpt_offset + header_len)
        assert f.read(4) == b"KTPT"
        count = read_uint16(f)
        f.read(2)
        kmp.kartpoints = KartStartPoints.from_file(f, count)

        f.seek(enpt_offset + header_len)
        kmp.enemypointgroups = EnemyPointGroups.from_file(f)

        f.seek(itpt_offset + header_len)
        kmp.itempointgroups = ItemPointGroups.from_file(f)

        #skip itpt
        f.seek(ckpt_offset + header_len)
        kmp.checkpoints = CheckpointGroups.from_file(f, ckph_offset)

        #bol.checkpoints = CheckpointGroups.from_file(f, sectioncounts[CHECKPOINT])

        f.seek(gobj_offset + header_len)
        assert f.read(4) == b"GOBJ"
        count = read_uint16(f)
        f.read(2)
        kmp.objects = MapObjects.from_file(f, count)

        f.seek(poti_offset + header_len)
        assert f.read(4) == b"POTI"
        count = read_uint16(f)
        total = read_uint16(f)

        # will handle the routes
        kmp.routes = ObjectContainer.from_file(f, count, Route)


        f.seek(area_offset + header_len)
        assert f.read(4) == b"AREA"
        count = read_uint16(f)
        f.read(2)
        kmp.areas = Areas.from_file(f, count)

        f.seek(came_offset + header_len)
        assert f.read(4) == b"CAME"
        count = read_uint16(f)
        start = read_uint8(f)
        f.read(1)
        kmp.cameras = Cameras.from_file(f, count)
        kmp.cameras.startcamid = start

        f.seek(jgpt_offset + header_len)
        assert f.read(4) == b"JGPT"
        count = read_uint16(f)
        f.read(2)
        kmp.respawnpoints = ObjectContainer.from_file(f, count, JugemPoint)

        f.seek(cnpt_offset + header_len)
        assert f.read(4) == b"CNPT"
        count = read_uint16(f)
        f.read(2)

        for i in range(count):
            kmp.cannonpoints.append( CannonPoint.from_file(f)  )

        f.seek(mspt_offset + header_len)
        assert f.read(4) == b"MSPT"
        count = read_uint16(f)
        f.read(2)
        for i in range(count):
            kmp.missionpoints.append( MissionPoint.from_file(f)  )

        f.seek(stgi_offset + header_len)
        assert f.read(4) == b"STGI"
        f.read(2)
        f.read(2)
        kmp.lap_count = read_uint8(f)
        kmp.kartpoints.pole_position = read_uint8(f)
        kmp.kartpoints.start_squeeze = read_uint8(f)
        kmp.lens_flare = read_uint8(f)
        read_uint8(f)
        kmp.flare_color = ColorRGB.from_file(f)
        kmp.flare_alpha = read_uint8(f)

        read_uint8(f)

        b0 = read_uint8(f)
        b1 = read_uint8(f)

        kmp.speed_modifier = unpack('>f', bytearray([b0, b1, 0, 0])  )[0]

        kmp.set_assoc()

        Area.level_file = kmp
        EnemyPointGroups.level_file = kmp

        return kmp

    def fix_file(self):
        return_string = ""

        """take care of routes for objects/camera/areas"""
        #set all the used by stuff for routes
        for object in self.objects.objects:
            object.set_route_info()
            if object.route != -1 and object.route < len(self.routes):
                self.routes[object.route].used_by.append(object)
            elif object.route >= len(self.routes):
                return_string += "Object {0} references route {1}, which does not exist. The reference will be removed.\n".format(get_kmp_name(object.objectid), object.route)
                object.route = -1
            elif object.route_info is None:
                object.route = -1
        for i, camera in enumerate(self.cameras):
            if camera.route != -1 and camera.route < len(self.routes):
                self.routes[camera.route].used_by.append(camera)
            elif camera.route >= len(self.routes):
                return_string += "Camera {0} references route {1}, which does not exist. The reference will be removed.\n".format(i, camera.route)
                camera.route = -1
            else:
                camera.route = -1
        for i, area in enumerate(self.areas):
            if area.type == 0:
                if area.cameraid != -1 and area.cameraid < len(self.cameras):
                    self.cameras[area.cameraid].used_by.append(area)
                elif area.cameraid >= len(self.cameras):
                    return_string += "Area {0} references camera {1}, which does not exist. The reference will be removed.\n".format(i, area.cameraid)
                    area.cameraid = -1
            if area.type == 3:
                if area.route != -1 and area.route < len(self.routes):
                    self.routes[area.route].used_by.append(area)
                elif area.route >= len(self.routes):
                    return_string += "Area {0} references route {1}, which does not exist. The reference will be removed.\n".format(i, area.route)

        #copy routes as necessary
        to_split = []
        for i, route in enumerate(self.routes):
            has_object = False
            has_camera = False
            has_area = False
            for object in route.used_by:
                if isinstance(object, MapObject):
                    has_object = True
                elif isinstance(object, Camera):
                    has_camera = True
                elif isinstance(object, Area):
                    has_area = True
            if len( [ x for x in (has_object, has_area, has_camera) if x ]  ) > 1:
                to_split.append((i, route))
        for i, route in to_split :
            # we know that these have both objects and cameras
            return_string += "Route {0} is used by more than one of: Camera, Object, Area (Moving Road). It has been split.\n".format(i)
            cameras_usedby = [ thing for thing in route.used_by if isinstance(thing, Camera)  ]
            objects_usedby = [ thing for thing in route.used_by if isinstance(thing, MapObject)  ]
            areas_usedby = [ thing for thing in route.used_by if isinstance(thing, Area)  ]
            for objs in (cameras_usedby, objects_usedby, areas_usedby):
                if objs:
                    new_route = route.copy()
                    new_route.used_by = objs
                    self.routes.append(new_route)
            self.routes.remove(route)

        #now that everything is split, we can spilt three groups
        object_routes = ObjectContainer()
        object_routes.assoc = ObjectRoute
        camera_routes = ObjectContainer()
        camera_routes.assoc = CameraRoute
        area_routes = ObjectContainer()
        area_routes.assoc = AreaRoute
        for route in self.routes:
            if route.used_by:
                if isinstance(route.used_by[0], Camera):
                    camera_routes.append(route.to_camera())
                elif isinstance(route.used_by[0], MapObject ):
                    object_routes.append(route.to_object())
                elif isinstance(route.used_by[0], Area ):
                    area_routes.append(route.to_area())
        self.routes = object_routes
        self.cameraroutes = camera_routes
        self.arearoutes = area_routes

        #set route_obj and partof
        for objs in (self.routes, self.cameraroutes, self.arearoutes):
            for route in objs:
                for object in route.used_by:
                    object.route_obj = route
                for point in route.points:
                    point.partof = route

        #remove self-linked routes
        for grouped_things in (self.enemypointgroups.groups, self.itempointgroups.groups, self.checkpoints.groups):
            #set the proper prevnext
            for i, group in enumerate(grouped_things):
                group.prevgroup = [grouped_things[i] for i in group.prevgroup if i != -1 and i < len(grouped_things)]
                group.nextgroup = [grouped_things[i] for i in group.nextgroup if i != -1 and i < len(grouped_things)]

            if len(grouped_things) < 2:
                continue
            for i,group in enumerate(grouped_things):
                if group in group.prevgroup and len(group.points) == 1:
                    return_string += "Group {0} was self-linked as a previous group. The link has been removed.\n".format(i)
                    group.remove_prev(group)
                if group in group.nextgroup  and len(group.points) == 1:
                    return_string += "Group {0} was self-linked as a next group. The link has been removed.\n".format(i)
                    group.remove_next(group)

        """sort cannonpoints by id"""
        self.cannonpoints.sort( key = lambda h: h.id)

        """remove invalid areas"""
        invalid_areas = []
        for i, area in enumerate(self.areas):
            if area.type < 0 or area.type > 10:
                invalid_areas.append(area)
                "Area {0} has type {1}, which is invalid. It will be removed.\n".format(i, area.type)
        for area in invalid_areas:
            self.areas.remove(area)

        """set cameras and enemypoints for areas"""
        num_cams = len(self.cameras)
        for area in self.areas.get_type(0):
            if area.cameraid < num_cams:
                area.camera = self.cameras[area.cameraid]
        for area in self.areas.get_type(4):
            if area.enemypointid == -1:
                return_string += "A area of type 4 was found that referenced an enemypoint that does not exist.\
                    It will be assigned to the closest enemypoint instead.\n"
                area.find_closest_enemypoint()
            area.enemypoint = self.enemypointgroups.get_point_from_index(area.enemypointid)
            if area.enemypoint is None:
                return_string += "A area of type 4 was found that referenced an enemypoint that does not exist.\
                    It will be assigned to the closest enemypoint instead.\n"
                area.find_closest_enemypoint()

        """separate areas into replay and not"""
        self.replayareas.extend( self.areas.get_type(0) )
        for area in self.replayareas:
            self.areas.remove(area)
        self.areas.sort( key = lambda h: h.type)

        """snap cameras to routes"""
        for camera in self.cameras:
            if camera.has_route() and camera.route_obj is not None and camera.route_obj.points:
                camera.position = camera.route_obj.points[0].position

        """separate cameras into replay and not"""
        #assign nextcams
        if self.cameras.startcamid < len(self.cameras):
            self.cameras.startcam = self.cameras[self.cameras.startcamid]
        for camera in self.cameras:
            if camera.nextcam != -1 and camera.nextcam < len(self.cameras) :
                camera.nextcam_obj = self.cameras[camera.nextcam]

        replaycams = list(set(self.replayareas.get_cameras()))
        nextcams = [(camera, camera.nextcam_obj) for camera in self.cameras if camera.nextcam_obj is not None]
        in_both = [ (camera, nextcam) for (camera, nextcam) in nextcams if nextcam in replaycams]

        for camera, nextcam in in_both:
            new_camera = nextcam.copy()
            camera.nextcam_obj = new_camera
            self.cameras.append(new_camera)

        self.replaycameras.extend( replaycams )
        self.replaycameras.to_replay()
        for camera in self.replaycameras:
            self.cameras.remove(camera)

        """remove invalid cameras"""
        self.remove_invalid_cameras()

        """do type assertions on replay cams"""
        repl_area_without_cams = [area for area in self.replayareas if area.camera is None]
        for area in repl_area_without_cams:
            return_string += "An area of type Camera did not reference a camera. It will be removed.\n"
            self.replayarea.remove(area)
        for area in self.replayareas:
            if area.camera.type not in (1, 2, 3, 4, 6):
                return_string += "An area of type Camera references a camera of type {0}, which is not a valid replay camera \
                    It will be converted to a type 1 camera (FixSearch)\n".format(area.camera.type)
                area.camera.type = 1
            area.camera.used_by.append(area)


        invalid_nonreplay = []
        for camera in self.cameras:
            if camera.type not in (0, 1, 4, 5, 7, 8, 9):
                return_string += "A camera of type {0} was found among the non-replay cams. It will be removed.\n".format(camera.type)
                invalid_nonreplay.append(camera)
        for camera in invalid_nonreplay:
            self.remove_camera(camera)

        self.cameras.to_opening()

        """split camera routes into replay routes and other routes"""
        self.replaycameraroutes.extend( [camera.route_obj for camera in self.replaycameras if camera.route_obj is not None]  )
        for route in self.replaycameraroutes:
            if route in self.cameraroutes:
                self.cameraroutes.remove(route)


        """set respawn_obj for checkpoints"""
        for group in self.checkpoints.groups:
            for point in group.points:
                if point.respawnid > -1 and point.respawnid < len(self.respawnpoints):
                    point.respawn_obj = self.respawnpoints[point.respawnid]
                else:
                    return_string += "A checkpoint was found to have an invalid respawn reference\
                        it has been reassigned to the closest resapwn point.\n"
                    point.assign_to_closest(self.respawnpoints)

        return return_string

    @classmethod
    def from_bytes(cls, data: bytes) -> 'KMP':
        KMP = cls.from_file(BytesIO(data))
        KMP.fix_file()
        return KMP

    def write(self, f):
        f.write(b"RKMD") #file magic
        size_off = f.tell()
        f.write(b"FFFF") #will be the length of the file
        f.write(pack(">H", 0xF)) #number of sections
        f.write(pack(">H", 0x4c)) #length of header
        f.write(pack(">I", 0x9d8)) #length of header
        sec_offs = f.tell()
        f.write(b"FFFF" * 15) #placeholder for offsets

        offsets = [ f.tell()]  #offset 1 for ktpt
        self.kartpoints.write(f)

        offsets.append( f.tell() ) #offset 2 for entp
        enph_off = self.enemypointgroups.write(f)
        offsets.append(enph_off) #offset 3 for enph

        offsets.append( f.tell() ) #offset 4 for itpt
        itph_off = self.itempointgroups.write(f)
        offsets.append(itph_off) #offset 5 for itph

        offsets.append(f.tell()) #offset 6 for ckpt
        self.checkpoints.set_rspid(self.respawnpoints)
        ktph_offset = self.checkpoints.write(f)
        offsets.append(ktph_offset) #offset 7 for ktph

        cameraroutes = self.cameras.get_routes()
        replaycameraroutes = self.replayareas.get_routes()

        offsets.append(f.tell() ) #offset 8 for gobj
        self.objects.write(f, len(replaycameraroutes) + len(cameraroutes) + len(self.arearoutes))

        routes = ObjectContainer()
        routes.extend(replaycameraroutes)
        routes.extend(cameraroutes)
        routes.extend(self.arearoutes)
        routes.extend(self.routes)

        offsets.append(f.tell() ) #offset 9 for poti
        f.write(b"POTI")
        f.write(pack(">H", len(routes) ) )
        count_off = f.tell()
        f.write(pack(">H", 0xFFFF ) )  # will be overridden later

        count = 0
        for route in routes:
            count += route.write(f)

        offset = f.tell()
        offsets.append(offset) #offset 10 for AREA

        f.seek(count_off)
        f.write(pack(">H", count) ) #fill in count of points for poti
        f.seek(offset)

        areas = Areas()
        areas.extend( self.areas  )
        areas.extend( self.replayareas )
        areas.write(f, len(cameraroutes) + len(replaycameraroutes) )

        cameras = Cameras()
        cameras.extend( self.replaycameras )
        cameras.extend( self.cameras )

        startcamid = 255
        for i, camera in enumerate(cameras):
            if camera == self.cameras.startcam:
                startcamid = i
                break
        offsets.append(f.tell() ) # offset 11 for CAME
        f.write(b"CAME")
        f.write(pack(">H", len(cameras) ) )
        f.write(pack(">BB", startcamid, 0) )

        for camera in cameras:
            camera.write(f, 0, len(self.replaycameras), routes)

        offset = f.tell()  #offset 12 for JPGT
        offsets.append(offset)

        f.write(b"JGPT")
        f.write(pack(">H", len(self.respawnpoints) ) )
        f.write(pack(">H", 0 ) )

        count = 0
        for point in self.respawnpoints:
            point.write(f, count)
        count += 1


        offset = f.tell()
        offsets.append(offset) #offset 13 for CNPT

        f.write(b"CNPT")
        count_off = f.tell()
        f.write(pack(">H", len(self.cannonpoints) ) )  # will be overridden later
        f.write(pack(">H", 0 ) )

        for point in self.cannonpoints:
            point.write(f)
        offset = f.tell()
        offsets.append(offset) #offset 14 for MSPT

        f.write(b"MSPT")
        count_off = f.tell()
        f.write(pack(">H", len(self.missionpoints) ) )  # will be overridden later
        f.write(pack(">H", 0 ) )


        count = 0
        for point in self.missionpoints:
            point.write(f, count)
        count += 1
        offset = f.tell()

        offsets.append(offset) #offset 15 for STGI
        f.write(b"STGI")
        f.write(pack(">HH", 1, 0 ) )
        f.write(pack(">B", self.lap_count))
        f.write(pack(">BB", self.kartpoints.pole_position, self.kartpoints.start_squeeze) )
        f.write(pack(">B", self.lens_flare))
        f.write(pack(">BBBBB", 0, self.flare_color.r, self.flare_color.b, self.flare_color.b, self.flare_alpha ) )
        f.write(pack(">b", 0 ) )

        byte_array = pack(">f", self.speed_modifier)
        f.write( byte_array[0:2])

        assert( len(offsets) == 15 )
        size = f.tell()
        f.seek(size_off)
        f.write(pack(">I", size ) )
        f.seek(sec_offs)
        for i in range(15):
            f.write(pack(">I", offsets[i]  - 0x4C ) )

    def to_bytes(self) -> bytes:
        f = BytesIO()
        self.write(f)
        return f.getvalue()

    def auto_generation(self):
        """
            - add opening cams
            - add replay cams"""
        self.copy_enemy_to_item()
        self.create_checkpoints_from_enemy()
        self.checkpoints.set_key_cps()
        self.create_respawns()
        self.cameras.add_goal_camera()

    def auto_cleanup(self):
        self.enemypointgroups.merge_groups()
        self.itempointgroups.merge_groups()
        self.checkpoints.merge_groups()

        self.remove_unused_routes()
        self.remove_unused_cameras()
        self.remove_unused_respawns()

        self.remove_invalid_cameras()
        self.areas.remove_invalid()
        self.remove_invalid_objects()

    #respawnid code
    def create_respawns(self):

        #remove all respwans
        self.respawnpoints.clear()
        for checkgroup in self.checkpoints.groups:
            num_checks = len(checkgroup.points)
            for i in range(4, num_checks, 8):
                checkpoint_mid1 = (checkgroup.points[i].start + checkgroup.points[i].end) /2
                checkpoint_mid2 = (checkgroup.points[i-1].start + checkgroup.points[i-1].end)/2

                respawn_new = JugemPoint( (checkpoint_mid1 + checkpoint_mid2) / 2 )

                for j in range( i - 4, i + 4):
                    if j < num_checks:
                        checkgroup.points[j].respawn_obj = respawn_new

                self.rotate_one_respawn(respawn_new)
                self.respawnpoints.append(respawn_new)

            #the ones at the end of the group have the same one as the previous
            for i in range( (int)(num_checks / 8), num_checks):
                checkgroup.points[i].respawn_obj = respawn_new

    def reassign_respawns(self):
        if len(self.checkpoints.groups) == 0:
            return


        for checkgroup in self.checkpoints.groups:
            for checkpoint in checkgroup.points:
                checkpoint.assign_to_closest(self.respawnpoints)

    def reassign_one_respawn(self, respawn : JugemPoint):
        if len(self.checkpoints.groups) == 0:
            return

        for checkgroup in self.checkpoints.groups:
            for checkpoint in checkgroup.points:
                old_assign = checkpoint.respawn_obj
                checkpoint.assign_to_closest(self.respawnpoints)
                checkpoint.respawn_obj = old_assign if checkpoint.respawn_obj != respawn else checkpoint.respawn_obj

    def remove_respawn(self, rsp: JugemPoint):
        if len(self.respawnpoints) <= 1:
            return
        self.respawnpoints.remove(rsp)
        for checkgroup in self.checkpoints.groups:
            for checkpoint in checkgroup.points:
                if checkpoint.respawn_obj == rsp:
                    checkpoint.assign_to_closest(self.respawnpoints)

    def get_index_of_respawn(self, rsp: JugemPoint):
        for i, respawn in enumerate( self.respawnpoints) :
            if rsp == respawn:
                return i
        return -1

    def remove_unused_respawns(self):
        unused_respawns = [i for i in list( range(1, len(self.respawnpoints) )) if i not in self.checkpoints.get_used_respawns()]
        unused_respawns.sort()
        unused_respawns.reverse()
        for rsp_idx in unused_respawns:
            self.remove_respawn( self.respawnpoints[rsp_idx]   )

    def find_closest_enemy_to_rsp(self, rsp: JugemPoint):
        enemy_groups = self.enemypointgroups.groups
        closest = None
        distance = 999999999
        group_idx = -1
        point_idx = -1
        master_point_idx = -1
        idx = 0
        for i, group in enumerate(enemy_groups):
            for j, point in enumerate(group.points):
                curr_distance = point.position.distance(rsp.position)
                if curr_distance < distance:
                    closest = point
                    distance = curr_distance
                    group_idx = i
                    point_idx = j
                    master_point_idx = idx
                idx += 1
        return closest, group_idx, point_idx, master_point_idx

    def rotate_one_respawn(self, rsp :JugemPoint):
        point, group_idx, pos_idx, point_idx = self.find_closest_enemy_to_rsp(rsp)
        enemy_groups = self.enemypointgroups.groups

        if point_idx == -1:
            return

        point_behind_dis =  999999999999
        point_ahead_dis =   999999999999

        if pos_idx != 0:
            point_behind = enemy_groups[group_idx].points[pos_idx - 1].position
            point_behind_dis = point_behind.distance(rsp.position)
        if pos_idx < len(enemy_groups[group_idx].points) - 1:
            point_ahead = enemy_groups[group_idx].points[pos_idx + 1].position
            point_ahead_dis = point_ahead.distance(rsp.position)

        #no other points in group, i am not bothering with finding the linking points
        if point_behind_dis == point_ahead_dis and point_behind_dis == 999999999999:
            return

        if point_behind_dis < point_ahead_dis:
            pos_ray = point.position - point_behind
        else:
            pos_ray = point_ahead - point.position

        if pos_ray.x == 0:
            pos_ray.x = 1

        theta = arctan( -pos_ray.z / pos_ray.x ) * 180 / 3.14
        if pos_ray.x > 0:
            theta += 180
        theta += 270
        rsp.rotation = Rotation(0, theta, 0)

    #enemy/item/checkpoint code
    def get_to_deal_with(self, obj):
        if isinstance(obj, (EnemyPointGroup, EnemyPoint, EnemyPointGroups) ):
            return self.enemypointgroups
        elif isinstance(obj, (ItemPointGroup, ItemPoint, ItemPointGroups) ):
            return self.itempointgroups
        else:
            return self.checkpoints

    def remove_group(self, del_group):
        to_deal_with = self.get_to_deal_with(del_group)

        to_deal_with.remove_group(del_group)

    def remove_point(self, del_point):
        to_deal_with = self.get_to_deal_with(del_point)

        to_deal_with.remove_point(del_point)

    def create_checkpoints_from_enemy(self):
        for checkgroup in self.checkpoints.groups:
            checkgroup.points.clear()
        self.checkpoints.groups.clear()

        #enemy_to_check = {-1 : -1}

        #create checkpoints from enemy points
        for i, group in enumerate( self.enemypointgroups.groups ):

            new_cp_group = CheckpointGroup()
            #new_cp_group.prevgroup = group.prevgroup
            #new_cp_group.nextgroup = group.nextgroup

            self.checkpoints.groups.append( new_cp_group )

            for j, point in enumerate( group.points ):
                draw_cp = False
                if i == 0 and j == 0:
                    draw_cp = True
                    #should both be vector3
                    central_point = self.kartpoints.positions[0].position
                    left_vector = self.kartpoints.positions[0].rotation.get_vectors()[2]
                    left_vector = Vector3( -1 * left_vector.x, left_vector.y,-1 * left_vector.z  )

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
        #post processing:
        while i < len(self.checkpoints.groups) and len(self.checkpoints.groups) > 1:
            group = self.checkpoints.groups[i]
            if len(group.points) == 0:
                self.checkpoints.remove_group(group)
            else:
                i += 1

    def copy_enemy_to_item(self):
        self.itempointgroups = ItemPointGroups()

        for group in self.enemypointgroups.groups:
            new_group = ItemPointGroup()
            new_group.prevgroup = [self.enemypointgroups.get_idx(prev) for prev in group.prevgroup]
            new_group.nextgroup = [self.enemypointgroups.get_idx(next) for next in group.nextgroup]

            for point in group.points:
                new_point = ItemPoint.new()
                new_point.position = point.position.copy()

                new_group.points.append(new_point)

            self.itempointgroups.groups.append(new_group)

        for group in self.itempointgroups.groups:
            group.prevgroup = [self.itempointgroups.groups[prev] for prev in group.prevgroup]
            group.nextgroup = [self.itempointgroups.groups[next] for next in group.nextgroup]

    #ruoutes code
    def get_route_container(self, obj):
        if isinstance(obj, (CameraRoute, OpeningCamera)):
            return self.cameraroutes
        if isinstance(obj, (CameraRoute, ReplayCamera)):
            return self.replaycameraroutes
        elif isinstance(obj, (AreaRoute, Area)):
            return self.arearoutes
        else:
            return self.routes

    def get_route_for_obj(self, obj):
        if isinstance(obj, (CameraRoute, Camera) ):
            return CameraRoute()
        elif isinstance(obj, (AreaRoute, Area)):
            return AreaRoute()
        else:
            return ObjectRoute()

    def get_index_of_route(self, route):
        route_container = self.get_route_container(route)
        for i, group in enumerate(route_container):
            if group == route:
                return i
        return -1

    def reset_routes(self, start_at = 0):
        self.reset_general_routes(self.routes, start_at)
        self.reset_general_routes(self.cameraroutes, start_at)
        self.reset_general_routes(self.arearoutes, start_at)

    def reset_general_routes(self, container, start_at = 0):
        for route_index in range(start_at, len(container) ):
            for object in container[route_index].used_by:
                object.route_obj = container[route_index]
    def remove_unused_routes(self):
        self.remove_unused_object_routes()
        self.remove_unused_camera_routes()
        self.remove_unused_area_routes()

    def remove_unused_general_route(self, container):
        to_remove = []
        for i, route in enumerate(container):
            if len(route.used_by) == 0:
                to_remove.append(i)
        to_remove.sort()
        to_remove.reverse()
        for rem_index in to_remove:
            container.pop(rem_index)

    def remove_unused_object_routes(self):
        self.remove_unused_general_route(self.routes)
        self.reset_general_routes(self.routes)

    def remove_unused_camera_routes(self):
        self.remove_unused_general_route(self.cameraroutes)
        self.reset_general_routes(self.cameraroutes)

    def remove_unused_area_routes(self):
        self.remove_unused_general_route(self.arearoutes)
        self.reset_general_routes(self.arearoutes)

    #cameras
    def remove_unused_cameras(self):
        used = []
        opening_cams = []

        for camera in self.cameras:
            if camera.type == 0:
                used.append(camera)

        next_cam : Camera = self.cameras.startcam
        while next_cam is not None and next_cam not in opening_cams:
            opening_cams.append(next_cam)
            next_cam = next_cam.nextcam_obj

        used.extend(opening_cams)

        #deleting stuff
        for camera in self.cameras:
            if not camera in used:
                if camera.route_obj is not None:
                    camera.route_obj.used_by.remove(camera)
                self.cameras.remove(camera)

    def removed_unused_replay_cameras(self):
        used_cams = self.replayareas.get_cameras()
        for camera in self.replaycameras:
            if camera not in used_cams:
                if camera.route_obj is not None:
                    camera.route_obj.used_by.remove(camera)
                self.replaycameras.remove(camera)


    def remove_camera(self, cam : Camera):
        if cam.type == 0 and len(self.cameras.get_type(0)) < 2:
            return
        if isinstance(cam, OpeningCamera):

            for camera in self.cameras:
                if camera.nextcam == cam:
                    camera.nextcam = None

            if self.cameras.startcam is cam:
                self.cameras.startcam = cam.nextcam

            self.cameras.remove(cam)
        elif isinstance(cam, ReplayCamera):
            self.replaycameras.remove(cam)
            for area in cam.used_by:
                area.camera = None

        if cam.route_obj is not None:
            cam.route_obj.used_by.remove(cam)
            if not cam.route_obj.used_by:
                #delete the route as well
                self.replaycameraroutes.remove(cam.route_obj)




    def remove_invalid_cameras(self):
        invalid_cams = [camera for camera in self.cameras if camera.type < 0 or camera.type > 9]
        for cam in invalid_cams:
            self.remove_camera(cam)

    #objects
    def remove_object(self, obj: MapObject):
        if obj.route_obj is not None:
            obj.route_obj.used_by.remove(obj)

        self.objects.objects.remove(obj)

    def remove_invalid_objects(self):
        invalid_objs = [obj for obj in self.objects.objects if obj.objectid not in OBJECTNAMES]
        for obj in invalid_objs:
            self.remove_object(obj)
with open("lib/mkwiiobjects.json", "r") as f:
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


def get_kmp_name(id):
    if id not in OBJECTNAMES:
        OBJECTNAMES[id] = "Unknown {0}".format(id)
        REVERSEOBJECTNAMES[OBJECTNAMES[id]] = id
        return "unknown " + str(id)
        #return
    #else:
    return OBJECTNAMES[id]


def temp_add_invalid_id(id):
    if id not in OBJECTNAMES:
        name = get_kmp_name(id)
        OBJECTNAMES[id] = name
        REVERSEOBJECTNAMES[name] = id