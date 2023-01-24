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
        self.id = 0
        self.prevgroup = [-1, -1, -1, -1, -1, -1]
        self.nextgroup = [-1, -1, -1, -1, -1, -1]

    def insert_point(self, enemypoint, index=-1):
        self.points.insert(index, enemypoint)

    def move_point(self, index, targetindex):
        point = self.points.pop(index)
        self.points.insert(targetindex, point)

    def copy_group(self, new_id, group):
        group.id = new_id
        for point in self.points:
            new_point = deepcopy(point)
            group.points.append(point)

        group.prevgroup = self.prevgroup.copy()
        group.nextgroup = self.nextgroup.copy()

        return group

    def copy_group_after(self, new_id, point, group):
        group.id = new_id
        pos = self.points.index(point)

        # Check if the element is the last element
        if not len(self.points)-1 == pos:
            for point in self.points[pos+1:]:
                group.points.append(point)

        group.nextgroup = self.nextgroup.copy()
        group.prevgroup = [self.id] + [-1] * 5

        self.nextgroup = [new_id] + [-1] * 5
        self.prevgroup = [new_id if id == self.id else id for id in self.prevgroup]

        return group

    def remove_after(self, point):
        pos = self.points.index(point)
        self.points = self.points[:pos+1]

    def copy_into_group(self, group):
        for point in group.points:
            self.points.append(point)

    def num_prev(self):
        return sum ( [1 for id in self.prevgroup if id != -1]  )

    def num_next(self):
        return sum ( [1 for id in self.nextgroup if id != -1]  )

    def add_new_prev(self, id):
        if id in self.prevgroup or id == -1:
            return
        self.prevgroup = [id for id in self.prevgroup if id != -1]
        if len(self.prevgroup) == 6:
            return False
        self.prevgroup.append(id)
        self.prevgroup += [-1] * (6 - len(self.prevgroup))

    def add_new_next(self, id):
        if id in self.nextgroup or id == -1:
            return
        self.nextgroup = [id for id in self.nextgroup if id != -1]
        if len(self.nextgroup) == 6:
            return False
        self.nextgroup.append(id)
        self.nextgroup += [-1] * (6 - len(self.nextgroup))

    def remove_prev(self, id):
        if id in self.prevgroup:
            self.prevgroup.remove(id)
            self.prevgroup.append(-1)

    def remove_next(self, id):
        if id in self.nextgroup:
            self.nextgroup.remove(id)
            self.nextgroup.append(-1)

class PointGroups(object):
    def __init__(self):
        self.groups = []
        self._group_ids = {}

    def points(self):
        for group in self.groups:
            for point in group.points:
                yield point

    def new_group_id(self):
        return len(self.groups)

    def split_group(self, group : PointGroup, point : KMPPoint):
        new_id = self.new_group_id()
        new_group = group.copy_group_after(new_id, point)

        self.groups.append(new_group)
        group.remove_after(point)

        for other_group in self.groups:
            if other_group != group and other_group != new_group:
                other_group.prevgroup = [new_id if id == group.id else id for id in other_group.prevgroup]

    def check_if_duplicate_possible(self, group):
        num_prevs_of_nexts = max( [ self.groups[idx].num_prev() for idx in group.nextgroup if idx != -1 ] )
        num_nexts_of_prevs = max( [ self.groups[idx].num_next() for idx in group.prevgroup if idx != -1 ] )
        return num_prevs_of_nexts < 6 and num_nexts_of_prevs < 6

    def duplicate_group(self, group):
        new_id = self.new_group_id()
        new_group = group.copy_group(new_id)
        self.groups.append(new_group)

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

        i = 0
        while i < len(self.groups):
            if len(self.groups) < 2:
                return

            group = self.groups[i]
            #print("compare the ids, they should be the same", i, group.id)
            if group.num_next() == 1 and self.groups[ group.nextgroup[0] ].num_prev() == 1:
                if 0 in group.nextgroup:
                    i += 1 #do not merge with the start
                    continue
                del_group = self.groups[ group.nextgroup[0] ]

                #print('merge ' + str(i) + " and " + str(del_group.id))
                if group.id == del_group.id:
                    print("ERROR: TRYING TO MERGE INTO ITSELF", group.id)
                    return
                    #continue

                group.copy_into_group( del_group )

                self.groups.remove(del_group)

                #replace this group's next with the deleted group's next
                group.nextgroup = del_group.nextgroup.copy()

                #around the deleted groups:
                for this_group in self.groups:
                    if this_group.id > del_group.id:
                        this_group.id -= 1
                for this_group in self.groups:
                    #replace links to the deleted group with the group it was merged into
                    this_group.prevgroup = [ id if id != del_group.id else group.id for id in this_group.prevgroup]

                    #this_group.nextgroup = [ id if id != del_group.id else this_group.id for id in group.nextgroup]

                    #deal with others
                    this_group.prevgroup = [ id if id < del_group.id or id == -1 else id - 1 for id in this_group.prevgroup ]
                    this_group.nextgroup = [ id if id < del_group.id or id == -1 else id - 1 for id in this_group.nextgroup  ]
            else:
                i += 1

    def get_new_point(self):
        return KMPPoint.new()

    def get_new_group(self):
        return PointGroup.new()

    def add_new_group(self):
        new_group = self.get_new_group()
        new_group.id = self.new_group_id()
        self.groups.append( new_group )

        if len(self.groups) == 1:
            new_group.add_new_next(0)
            new_group.add_new_prev(0)

    def remove_group(self, del_group, merge = True):
        self.groups.remove(del_group)

        for group in self.groups :
            if group.id > del_group.id:
                group.id -= 1

            #remove previous links to the deleted group
            group.prevgroup = [ id for id in group.prevgroup if id != del_group.id]
            group.nextgroup = [ id for id in group.nextgroup if id != del_group.id]

            #pad back to 6 entries
            group.prevgroup += [-1] * (6- len(group.prevgroup))
            group.nextgroup += [-1] * (6- len(group.nextgroup))


            #deal with others
            group.prevgroup = [ id if id < del_group.id or id == -1 else id - 1 for id in group.prevgroup ]
            group.nextgroup = [ id if id < del_group.id or id == -1 else id - 1 for id in group.nextgroup  ]

        if merge:
            self.merge_groups()

        if len(self.groups) == 1:
            self.groups[0].add_new_next(0)
            self.groups[0].add_new_prev(0)

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

            to_visit.extend( [id for id in self.groups[idx].nextgroup if id != -1 and id not in visited] )

        unused_groups = [self.groups[i] for i in list( range(1, len(self.groups) )) if i not in visited]
        num_points = [len(group.points) for group in unused_groups]
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

    def copy_group(self, new_id):
        group = EnemyPointGroup()
        return super().copy_group(new_id, group)

    def copy_group_after(self, new_id, point):
        group = EnemyPointGroup()
        return super().copy_group_after(new_id, point, group)

    def write_points_enpt(self, f):
        for point in self.points:
            point.write(f)
        return len(self.points)

    def write_enph(self, f, index):
         f.write(pack(">B", index ) )
         f.write(pack(">B", len(self.points) ) )
         for i in range(6):
            f.write(pack(">b", self.prevgroup[i]))
         for i in range(6):
            f.write(pack(">b", self.nextgroup[i]))
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
        type_4_areas = __class__.level_file.areas.get_type(4)
        for area in type_4_areas:
            if area.enemypoint == del_point:
                area.enemypoint = None
                area.enemypointid = -1

        super().remove_point(del_point)

    def remove_group(self, del_group, merge = True):
        type_4_areas = __class__.level_file.areas.get_type(4)
        for area in type_4_areas:
            if area.enemypoint in del_group.points:
                area.enemypoint = None
                area.enemypointid = -1

        super().remove_group(del_group, merge = True)

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
            group.write_enph(f, point_indices[idx])

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

    def copy_group(self, new_id):
        group = ItemPointGroup()
        return super().copy_group(new_id, group)

    def copy_group_after(self, new_id, point):
        group = ItemPointGroup()
        return super().copy_group_after(new_id, point, group)

    def write_itpt(self, f):
        for point in self.points:
            point.write(f)
        return len(self.points)

    def write_itph(self, f, index):
         self.prevgroup += [-1] * (6 - len(self.prevgroup) )
         self.nextgroup += [-1] * (6 - len(self.nextgroup) )

         f.write(pack(">B", index ) )
         f.write(pack(">B", len(self.points) ) )
         for i in range(6):
            f.write(pack(">b", self.prevgroup[i]))
         for i in range(6):
            f.write(pack(">b", self.nextgroup[i]))
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
            group.write_itph(f, point_indices[idx])


        return  itph_offset

class Checkpoint(KMPPoint):
    def __init__(self, start, end, respawn=0, type=0):
        self.start = start
        self.end = end
        self.mid = (start+end)/2.0
        self.respawn = respawn
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
            self.respawn = smallest[0]


    @classmethod
    def from_file(cls, f):
        checkpoint = cls.new()

        checkpoint.start = Vector3(*unpack(">f", f.read(4) ), 0, *unpack(">f", f.read(4) ) )
        checkpoint.end = Vector3(*unpack(">f", f.read(4) ), 0, *unpack(">f", f.read(4) ) )

        checkpoint.respawn = read_uint8(f) #respawn

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
        f.write(pack(">b", self.respawn))

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

    def copy_group(self, new_id):
        group = CheckpointGroup()
        return super().copy_group(new_id, group)


    def copy_group_after(self, new_id, point):
        group = CheckpointGroup()
        return super().copy_group_after(new_id, point, group)

    def get_used_respawns(self):
        return set( [checkpoint.respawn for checkpoint in self.points]  )

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


    def write_ckpt(self, f, key, prev):

        if len(self.points) > 0:
            key = self.points[0].write(f, -1, 1 + prev, key)

            for i in range(1, len( self.points) -1 ):
                key = self.points[i].write(f, i-1 + prev, i + 1 + prev, key)
            if len(self.points) > 1:
                key = self.points[-1].write(f, len(self.points) - 2 + prev, -1, key)
        return key

    def write_ckph(self, f, index):
        #print(index, len(self.points), self.prevgroup, self.nextgroup)
        f.write(pack(">B", index ) )
        f.write(pack(">B", len(self.points) ) )
        f.write(pack(">bbbbbb", self.prevgroup[0], self.prevgroup[1], self.prevgroup[2], self.prevgroup[3], self.prevgroup[4], self.prevgroup[5]) )
        f.write(pack(">bbbbbb", self.nextgroup[0], self.nextgroup[1], self.nextgroup[2], self.nextgroup[3], self.nextgroup[4], self.nextgroup[5]) )
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
        print("ckpt offset", hex(f.tell()))
        assert f.read(4) == b"CKPT"
        count = read_uint16(f)
        f.read(2)

        print(count)

        all_points = []
        #read the enemy points
        for i in range(count):
            checkpoint = Checkpoint.from_file(f)
            all_points.append(checkpoint)

        print("ckph offset", hex(f.tell()))
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

            for id in group.nextgroup:
                starting_key_cp[id] = max( starting_key_cp[id], num_key)

            sum_points += len(group.points)
        ckph_offset = f.tell()

        f.write(b"CKPH")
        f.write(pack(">H", len(self.groups) ) )
        f.write(pack(">H", 0) )

        for idx, group in enumerate( self.groups ):
            group.write_ckph(f, indices_offset[idx])
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
    def new(cls):
        return cls()

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

    @classmethod
    def new(cls):
        return cls()

    def has_area(self):
        for obj in self.used_by:
            if isinstance(obj, Area):
                return True
        return False

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

        point.unk1 = read_uint16(f) & 0xFF
        point.unk2 = read_uint16(f) & 0xFF
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
        if self.unk1 == 0 and not force_actual:
            f.write(pack(">HH", 30, 0) )
        else:
            f.write(pack(">HH", self.unk1 & 0xFFFF, self.unk2) )

# Section 5
# Objects
class MapObject(object):

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
    def new(cls, obj_id = 101):
        return cls(Vector3(0.0, 0.0, 0.0), obj_id)

    @classmethod
    def default_item_box(cls):
        item_box = cls(Vector3(0.0, 0.0, 0.0), 101)
        return item_box

    def split_prescence(self, prescence):
        self.single = prescence & 0x1
        self.double = prescence & 0x2
        self.triple = prescence & 0x4

    @classmethod
    def from_file(cls, f):
        object = cls.new()

        object.objectid = read_uint16(f)


        f.read(2)
        object.position = Vector3(*unpack(">fff", f.read(12)))
        object.rotation = Rotation.from_file(f)

        object.scale = Vector3(*unpack(">fff", f.read(12)))
        object.route = read_int16(f)
        object.userdata = unpack(">hhhhhhhh", f.read(2 * 8))
        object.split_prescence( read_uint16(f) )

        return object

    def write(self, f):

        f.write(pack(">H", self.objectid  ))


        f.write(pack(">H", 0) )
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        self.rotation.write(f)
        f.write(pack(">fff", self.scale.x, self.scale.y, self.scale.z))
        f.write(pack(">h", self.route) )


        for i in range(8):
            f.write(pack(">h", self.userdata[i]))

        presence = self.single | (self.double << 1) | (self.triple << 2)


        f.write( pack(">H", presence) )
        return 1
    def copy(self):


        this_class = self.__class__
        obj = this_class.new()
        obj.position = Vector3(self.position.x, self.position.y, self.position.z)
        obj.rotation =  self.rotation.copy()
        obj.scale = Vector3(self.scale.x, self.scale.y, self.scale.z)
        obj.objectid = self.objectid
        obj.route = self.route

        obj.single = self.single
        obj.double = self.double
        obj.triple = self.triple

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
            if obj is not None:
                mapobjs.objects.append(obj)

        return mapobjs

    def write(self, f):

        num_written = 0


        f.write(b"GOBJ")
        count_offset = f.tell()
        f.write(pack(">H", len(self.objects)))
        f.write(pack(">H", 0) )

        #print(bol2kmp)
        for object in self.objects:
            object.write(f )

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
        area.scale.x = area.scale.x
        area.scale.y = area.scale.y
        area.scale.z = area.scale.z

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

    def write(self, f):
        f.write(pack(">B", self.shape) ) #shape
        type = self.type if self.type >= 0 and self.type <= 10 else 11
        f.write(pack(">B", type ) )

        f.write(pack(">b", self.cameraid) )
        f.write(pack(">B", self.priority & 0xFF) ) #priority

        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        self.rotation.write(f)
        f.write(pack(">fff", self.scale.x, self.scale.y, self.scale.z))

        self.set_enemypointid()
        enemypointid = 255 if self.enemypointid < 0 else self.enemypointid
        self.set_route()
        route = 255 if self.route < 0 else self.route
        f.write(pack(">HHBBH", self.setting1, self.setting2, route, enemypointid, 0 ) )
        return 1

    def copy(self):
        new_area = self.__class__.new()
        new_area.position = Vector3(self.position.x, self.position.y, self.position.z)
        new_area.rotation = self.rotation.copy()
        new_area.scale = Vector3(self.scale.x, self.scale.y, self.scale.z)
        new_area.shape = self.shape
        new_area.type = self.type
        new_area.cameraid = self.cameraid
        new_area.setting1 = self.setting1
        new_area.setting2 = self.setting2
        new_area.route = self.route
        new_area.enemypointid = self.enemypointid

        return new_areainvalid

    #type 0 - camera
    def set_camera(self):
        if self.type == 0:
            cameras = __class__.level_file.cameras
            if self.cameraid < len(cameras) and cameras[self.cameraid] == self.cameraid:
                return self.cameraid

            for i, camera in enumerate(cameras):
                if camera == self.camera:
                    self.cameraid = i
                    return i

    def set_cam_from_id(self):
        if self.type == 0:
            cameras = __class__.level_file.cameras
            if self.cameraid < len(cameras):
                self.camera = cameras[self.cameraid]

    #type 3 - moving road
    def set_route(self):
        if self.type == 3:
            routes = __class__.level_file.routes
            if self.route != -1 and self.route < len( routes ) and routes[self.route] == self.route_obj:
                return self.route

            for i, route in enumerate(routes):
                if route == self.route_obj:
                    self.route = i
                    return i

    def set_route_from_id(self):
        if self.type == 3:
            routes = __class__.level_file.routes
            if self.route < len( routes ):
                self.camera = routes[self.route]

    #type 4 - force recalc
    def set_enemypointid(self):
        if self.type == 4:
            point_idx = __class__.level_file.enemypointgroups.get_index_from_point(self.enemypoint)
            self.enemypointid = point_idx
            return point_idx

    def set_enemypoint_from_id(self):
        self.enemypoint = __class__.level_file.enemypointgroups.get_point_from_index(self.enemypointid)

    def find_closest_enemypoint(self):
        enemygroups = __class__.level_file.enemypointgroups.groups
        min_distance = 9999999999999
        pointid = 0
        for group in enemygroups:
            for point in group.points:
                distance = self.position.distance( point.position)
                if distance < min_distance:
                    self.enemypointid = pointid
                    self.enemypoint = point
                    min_distance = distance

                pointid += 1

    def remove_self(self):
        if self.cameraid != -1 and self.cameraid < len(__class__.level_file.cameras):
            __class__.level_file.cameras[self.cameraid].used_by.remove(self)
        if self.route != -1 and self.route < len(__class__.level_file.routes):
            __class__.level_file.routes[self.route].used_by.remove(self)

class Areas(object):
    def __init__(self):
        self.areas = []

    @classmethod
    def from_file(cls, f, count):
        areas = cls()
        for i in range(count):
            new_area = Area.from_file(f)
            if new_area is not None:
                areas.areas.append(new_area)

        return areas

    def write(self, f):
        f.write(b"AREA")
        area_count_off = f.tell()
        f.write(pack(">H", 0xFFFF) )
        f.write(pack(">H", 0) )

        num_written = 0
        for area in self.areas:
            num_written += area.write(f)

        end_sec = f.tell()
        f.seek(area_count_off)
        f.write(pack(">H", num_written) )
        f.seek(end_sec)

    def get_type(self, area_type):
        return [area for area in self.areas if area.type == area_type]

    def remove_area(self, area : Area):
        area.remove_self()
        self.areas.remove(area)

    def remove_invalid(self):
        invalid_areas = [area for area in self.areas if area.type < 0 or area.type > 10]
        for area in invalid_areas:
            self.remove_area( area )

# Section 8
# Cameras
class FOV:
    def __ini__(self):
        self.start = 0
        self.end = 0
class Cameras(ObjectContainer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.startcam = -1
        self.widget = None

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

class Camera(object):
    can_copy = True
    def __init__(self, position):
        self.type = 0
        self.nextcam = -1
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
        self.startcamera = 0

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
        new_camera = self.__class__.new()
        new_camera.position = Vector3(self.position.x, self.position.y, self.position.z)
        new_camera.position2 = Vector3(self.position2.x, self.position2.y, self.position2.z)
        new_camera.position3 = Vector3(self.position3.x, self.position3.y, self.position3.z)
        new_camera.rotation = self.rotation.copy()

        new_camera.type = self.type
        new_camera.nextcam = self.nextcam
        new_camera.shake = self.shake
        new_camera.route = self.route
        new_camera.routespeed = self.routespeed
        new_camera.zoomspeed = self.zoomspeed
        new_camera.viewspeed = self.viewspeed

        new_camera.startflag = self.startflag
        new_camera.movieflag = self.movieflag

        new_camera.fov.start = self.fov.start
        new_camera.fov.end = self.fov.end

        new_camera.camduration = self.camduration


        return new_camera


    def write(self, f):

        f.write(pack(">B", self.type ) )
        f.write(pack(">bBb", self.nextcam, 0, self.route) )



        f.write(pack(">H", self.routespeed ) )
        f.write(pack(">H", self.zoomspeed ) )
        f.write(pack(">H", self.viewspeed ) )

        f.write(pack(">B", self.startflag ) )
        f.write(pack(">B", self.movieflag ) )


        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        self.rotation.write(f)

        f.write(pack(">ff", self.fov.start, self.fov.end))


        f.write(pack(">fff", self.position3.x, self.position3.y, self.position3.z))
        if self.type == 4:
            f.write(pack(">fff", self.position3.x, self.position3.y, self.position3.z))
        else:
            f.write(pack(">fff", self.position2.x, self.position2.y, self.position2.z))
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
        self.cameras = Cameras()
        self.cameraroutes = ObjectContainer()

        self.respawnpoints = ObjectContainer()
        self.cannonpoints = ObjectContainer()

        self.missionpoints = ObjectContainer()

        Area.level_file = self
        EnemyPointGroups.level_file = self

        self.set_assoc()

    def set_assoc(self):
        self.routes.assoc = ObjectRoute
        self.cameraroutes.assoc = CameraRoute
        self.respawnpoints.assoc = JugemPoint
        self.cannonpoints.assoc = CannonPoint
        self.missionpoints.assoc = MissionPoint

    @classmethod
    def make_useful(cls):
        kmp = cls()
        kmp.enemypointgroups.groups.append(EnemyPointGroup.new())
        kmp.enemypointgroups.groups[0].add_new_prev(0)
        kmp.enemypointgroups.groups[0].add_new_next(0)
        kmp.itempointgroups.groups.append(ItemPointGroup.new())
        kmp.itempointgroups.groups[0].add_new_prev(0)
        kmp.itempointgroups.groups[0].add_new_next(0)
        kmp.checkpoints.groups.append(CheckpointGroup.new() )
        kmp.checkpoints.groups[0].add_new_prev(0)
        kmp.checkpoints.groups[0].add_new_next(0)
        kmp.kartpoints.positions.append( KartStartPoint.new() )

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
        objects.extend(self.areas.areas)
        objects.extend(self.cameras)
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
        kmp.cameras.startcam = start

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

        #set all the used by stuff
        for object in self.objects.objects:
            object.set_route_info()
            if object.route != -1:
                self.routes[object.route].used_by.append(object)
        for i, camera in enumerate(self.cameras):
            #print(camera.route)
            if camera.route != -1 and camera.route < len(self.routes):
                self.routes[camera.route].used_by.append(camera)
            elif camera.route > len(self.routes):
                "Camera {0} references route {1}, which does not exist. The reference will be removed.\n".format(i, camera.route)
                camera.route = -1
            else:
                camera.route = -1
        for area in self.areas.areas:
            if area.type == 0 and area.cameraid != -1 and area.cameraid < len(self.cameras):
                self.cameras[area.cameraid].used_by.append(area)
            if area.type == 3 and area.route != -1 and area.route < len(self.routes):
                self.routes[area.route].used_by.append(area)

        to_split = []
        for i, route in enumerate(self.routes):
            has_object = False
            has_camera = False
            for object in route.used_by:
                if isinstance(object, (MapObject, Area)):
                    has_object = True
                elif isinstance(object, Camera):
                    has_camera = True
            if has_camera and has_object:
                to_split.append((i, route))

        for i, route in to_split :
            # we know that these have both objects and cameras
            new_route = route.copy()
            return_string += "Route {0} is used by an object and camera. It has been split.\n".format(i)
            new_route.used_by = [ thing for thing in route.used_by if isinstance(thing, Camera)  ]
            route.used_by = [ thing for thing in route.used_by if isinstance(thing, (MapObject, Area))  ]
            self.routes.append(new_route)

        #now that everything is split, we can spilt into cam routes and non cam routes
        object_routes = ObjectContainer()
        object_routes.assoc = ObjectRoute
        camera_routes = ObjectContainer()
        camera_routes.assoc = CameraRoute
        for route in self.routes:
            if len(route.used_by) > 0:
                if isinstance(route.used_by[0], Camera):
                    camera_routes.append(route.to_camera())
                elif isinstance(route.used_by[0], (MapObject, Area) ):
                    object_routes.append(route.to_object())
            else:
                object_routes.append(route.to_object())
        self.routes = object_routes
        self.cameraroutes = camera_routes

        #set used by again:
        for i, route in enumerate(self.routes):
            for object in route.used_by:
                object.route = i
                object.route_obj = route
            for point in route.points:
                point.partof = route
        for i, route in enumerate(self.cameraroutes):
            for object in route.used_by:
                object.route = i
                object.route_obj = route
            for point in route.points:
                point.partof = route

        #do ids of enemyroutes, itemroutes, and checkgroups so that they are sequential
        for grouped_things in (self.enemypointgroups.groups, self.itempointgroups.groups, self.checkpoints.groups):
            if len(grouped_things) < 2:
                continue
            for i,group in enumerate(grouped_things):
                if i in group.prevgroup:
                    return_string += "Group {0} was self-linked as a previous group. The link has been removed.\n".format(i)
                    group.prevgroup = [ id for id in group.prevgroup if id != i ]
                    group.prevgroup += [-1] * (6-len(group.prevgroup))
                if i in group.nextgroup:
                    return_string += "Group {0} was self-linked as a next group. The link has been removed.\n".format(i)
                    group.nextgroup = [ id for id in group.nextgroup if id != i]
                    group.nextgroup += [-1] * (6-len(group.nextgroup))

        self.cannonpoints.sort( key = lambda h: h.id)

        #assign cameras
        num_cams = len(self.cameras)
        for area in self.areas.get_type(0):
            if area.cameraid < num_cams:
                area.camera = self.cameras[area.cameraid]
        num_routes = len(self.routes)
        for area in self.areas.get_type(3):
            if area.route < num_routes:
                area.route_obj = self.routes[area.route]

        for area in self.areas.get_type(4):
            area.enemypoint = self.enemypointgroups.get_point_from_index(area.enemypointid)

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
         ktph_offset = self.checkpoints.write(f)
         offsets.append(ktph_offset) #offset 7 for ktph

         offsets.append(f.tell() ) #offset 8 for gobj
         self.objects.write(f)

         routes, cameras = self.combine_routes()
         #print(len(routes), [camera.route for camera in cameras])

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
         f.write(pack(">H", count ) )  # will be overridden later
         f.seek(offset)

         self.areas.write(f)

         offsets.append(f.tell() ) # offset 11 for CAME
         f.write(b"CAME")
         count_off = f.tell()
         f.write(pack(">H", 0xFFFF ) )  # will be overridden later
         f.write(pack(">H", 0xFFFF ) )  # will be overridden later

         count = 0

         for camera in cameras:
            count += camera.write(f)

         offset = f.tell()  #offset 12 for JPGT
         offsets.append(offset)

         f.seek(count_off)
         f.write(pack(">H", count ) )
         if self.cameras.startcam == -1:
            f.write(pack(">bB", -1, 0 ) )
         else:
            f.write(pack(">BB", self.cameras.startcam, 0 ) )
         f.seek(offset)



         f.write(b"JGPT")
         f.write(pack(">H", len(self.respawnpoints) ) )  # will be overridden later
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

    def combine_routes(self):
        routes = ObjectContainer()
        cameras = Cameras()

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

    #respawn code
    def create_respawns(self):

        #remove all respwans
        self.respawnpoints.clear()
        rsp_idx = 0

        for checkgroup in self.checkpoints.groups:
            num_checks = len(checkgroup.points)
            for i in range(4, num_checks, 8):
                checkpoint_mid1 = (checkgroup.points[i].start + checkgroup.points[i].end) /2
                checkpoint_mid2 = (checkgroup.points[i-1].start + checkgroup.points[i-1].end)/2

                respawn_new = JugemPoint( (checkpoint_mid1 + checkpoint_mid2) / 2 )

                for j in range( i - 4, i + 4):
                    if j < num_checks:
                        checkgroup.points[j].respawn = rsp_idx

                rsp_idx += 1

                self.rotate_one_respawn(respawn_new)
                self.respawnpoints.append(respawn_new)

            #the ones at the end of the group have the same one as the previous
            for i in range( (int)(num_checks / 8), num_checks):
                checkgroup.points[i].respawn = rsp_idx - 1

    def reassign_respawns(self):
        if len(self.checkpoints.groups) == 0:
            return


        for checkgroup in self.checkpoints.groups:
            for checkpoint in checkgroup.points:
                checkpoint.assign_to_closest(self.respawnpoints)

    def reassign_one_respawn(self, respawn : JugemPoint):
        if len(self.checkpoints.groups) == 0:
            return

        rsp_id = self.get_index_of_respawn(respawn)

        for checkgroup in self.checkpoints.groups:
            for checkpoint in checkgroup.points:
                old_assign = checkpoint.respawn
                checkpoint.assign_to_closest(self.respawnpoints)
                checkpoint.respawn = old_assign if checkpoint.respawn != rsp_id or old_assign == rsp_id else checkpoint.respawn

    def remove_respawn(self, rsp: JugemPoint):
        respawn_idx = self.get_index_of_respawn(rsp)
        self.respawnpoints.remove(rsp)
        if respawn_idx != -1:
            #edit the respawn link of all checkpoints
            for checkgroup in self.checkpoints.groups:
                for checkpoint in checkgroup.points:
                    if checkpoint.respawn > respawn_idx:
                        checkpoint.respawn -= 1
                    elif checkpoint.respawn == respawn_idx:
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
            new_cp_group.id = i
            new_cp_group.prevgroup = group.prevgroup
            new_cp_group.nextgroup = group.nextgroup

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
            new_group.id = group.id
            new_group.prevgroup = group.prevgroup.copy()
            new_group.nextgroup = group.nextgroup.copy()

            for point in group.points:
                new_point = ItemPoint.new()
                new_point.position = point.position.copy()

                new_group.points.append(new_point)

            self.itempointgroups.groups.append(new_group)

    #ruoutes code
    def get_route_container(self, obj):
        if isinstance(obj, (CameraRoute, Camera)):
            return self.cameraroutes
        else:
            return self.routes

    def get_route_for_obj(self, obj):
        if isinstance(obj, (CameraRoute, Camera) ):
            return CameraRoute()
        else:
            return ObjectRoute()

    def get_index_of_route(self, route):
        route_container = self.get_route_container(route)
        for i, group in enumerate(route_container):
            if group == route:
                return i
        return -1

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

    #cameras
    def remove_unused_cameras(self):
        used = []
        opening_cams = []

        #type 8 stays

        for camera in self.cameras:
            if camera.type == 0:
                used.append(camera)
        if self.cameras.startcam != -1 and (self.cameras.startcam < len(self.cameras)):
            first_cam : Camera = self.cameras[self.cameras.startcam]
            used.append(first_cam)
            opening_cams.append(first_cam)
            next_cam = first_cam.nextcam
            while next_cam != -1 and next_cam < len(self.cameras):
                next_camera = self.cameras[next_cam]
                if next_camera in used:
                    break
                used.append(next_camera)
                opening_cams.append(next_camera)
                next_cam = next_camera.nextcam

        #now iterate through area
        for area in self.areas.get_type(0):
            if area.cameraid != -1 and area.cameraid < len(self.cameras):
                used.append( self.cameras[area.cameraid]  )

        #deleting stuff
        for i in range( len(self.cameras) -1, -1, -1):
            cam_to_del = self.cameras[i]
            if not cam_to_del in used:
                if cam_to_del.route != -1 and cam_to_del.route < len(self.cameraroutes):
                    self.cameraroutes[cam_to_del.route].used_by.remove(cam_to_del)
                self.cameras.remove(cam_to_del)

        for i, camera in enumerate (self.cameras):
            for area in camera.used_by:
                area.cameraid = i

        #deal with starting cams
        curr_cam = opening_cams[0]
        for i in range(1, len(opening_cams)):
            next_idx = self.cameras.index( opening_cams[i] )
            curr_cam.nextcam = next_idx
            curr_cam = self.cameras[next_idx]

    def remove_camera(self, cam : Camera):
        if cam.route != -1 and cam.route < len(self.cameraroutes):
            self.cameraroutes[cam.route].used_by.remove(cam)

        self.cameras.remove(cam)

    def remove_invalid_cameras(self):
        invalid_cams = [camera for camera in self.cameras if camera.type < 0 or camera.type > 9]
        for cam in invalid_cams:
            self.remove_camera(cam)

    #objects
    def remove_object(self, obj: MapObject):
        if obj.route != -1 and obj.route < len(self.routes):
            self.routes[obj.route].used_by.remove(obj)

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