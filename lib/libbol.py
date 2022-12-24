import json
from struct import unpack, pack
from numpy import ndarray, array
from binascii import hexlify
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
        #print(forward.x, -forward.z, forward.y)
        #print(self.mtx)
        #print([x for x in self.mtx])

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
        #print(vec)

        
        return vec
    
    @classmethod
    def from_euler(cls, degs):
        r = R.from_euler('xyz', [degs.x, degs.y, degs.z], degrees=True)
        vecs = r.as_matrix()
        vector_z = Vector3(vecs[0][0], vecs[1][0], vecs[2][0])
        vector_y = Vector3(vecs[0][1], vecs[1][1], vecs[2][1])
        vector_x = Vector3(vecs[0][2], vecs[1][2], vecs[2][2])

        # forward up left
        return cls(vector_x, vector_y, vector_z)
        

class ObjectContainer(list):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def from_file(cls, f, count, objcls):
        container = cls()

        for i in range(count):
            obj = objcls.from_file(f)
            container.append(obj)

        return container

    @classmethod
    def from_file_kmp(cls, f, count, objcls):
        container = cls()

        for i in range(count):
            obj = objcls.from_file_kmp(f)
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
    def __init__(self, position, pointsetting, link, scale, groupsetting, group, pointsetting2, unk1=0, unk2=0):
        self.position = position
        self.pointsetting = pointsetting
        self.link = link
        self.scale = scale
        self.groupsetting = groupsetting
        self.group = group
        self.pointsetting2 = pointsetting2
        self.unk1 = unk1
        self.unk2 = unk2

    @classmethod
    def new(cls):
        return cls(
            Vector3(0.0, 0.0, 0.0),
            0, -1, 1000.0, 0, 0, 0
        )

    @classmethod
    def from_file(cls, f, old_bol=False):
        start = f.tell()
        args = [Vector3(*unpack(">fff", f.read(12)))]
        if not old_bol:
            args.extend(unpack(">HhfHBBBH", f.read(15)))
            padding = f.read(5)  # padding
            assert padding == b"\x00" * 5
        else:
            args.extend(unpack(">HhfHBB", f.read(12)))
            args.extend((0, 0))

        obj = cls(*args)
        obj._size = f.tell() - start
        if old_bol:
            obj._size += 8
        return obj

    @classmethod
    def from_file_kmp(cls, f):
    
        point = cls.new()

        point.position = Vector3(*unpack(">fff", f.read(12)))
        point.scale = read_float(f) * 100
        point.pointsetting = read_uint16(f)
        point.group_setting = read_uint8(f)
        point.pointsetting2 = read_uint8(f)
        
        return point

    def write(self, f):
        start = f.tell()
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        f.write(pack(">Hhf", self.pointsetting, self.link, self.scale))
        f.write(pack(">HBBBH", self.groupsetting, self.group, self.pointsetting2, self.unk1, self.unk2))
        f.write(b"\x00"*5)
        #assert f.tell() - start == self._size

    def write_kmp_enpt(self, f):
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        f.write(pack(">f", self.scale/100 ) )
        f.write(pack(">H", self.pointsetting) )
        f.write(pack(">bB", self.groupsetting & 0xFF, self.pointsetting2) )
        
    def write_kmp_itpt(self, f):
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        f.write(pack(">f", 0 ) )
        f.write(pack(">HH", self.unk1, self.unk2) )

class EnemyPointGroup(object):
    def __init__(self):
        self.points = []
        self.id = 0
        self.prev = []
        self.next = []

    @classmethod
    def new(cls):
        return cls()

    @classmethod
    def from_file_kmp(cls, f, idx, points):
        group = cls()
        group.id = idx
        start_idx = read_uint8(f)
        len = read_uint8(f)
        
 
        group.prev = list(filter((-1).__ne__, unpack(">bbbbbb", f.read(6)) ) )
        group.next = list(filter((-1).__ne__, unpack(">bbbbbb", f.read(6)) ) )
        f.read( 2)
        
        for i in range(start_idx, start_idx + len):
            group.points.append(points[i])
            points[i].group = idx
        
        return group

    def insert_point(self, enemypoint, index=-1):
        self.points.insert(index, enemypoint)

    def move_point(self, index, targetindex):
        point = self.points.pop(index)
        self.points.insert(targetindex, point)

    def copy_group(self, new_id):
        group = EnemyPointGroup()
        group.id = new_id
        for point in self.points:
            new_point = deepcopy(point)
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
                new_point = deepcopy(point)
                new_point.group = new_id
                group.points.append(new_point)

        return group

    def remove_after(self, point):
        pos = self.points.index(point)
        self.points = self.points[:pos+1]

    def write_kmp_points_enpt(self, f):
        for point in self.points:
            point.write_kmp_enpt(f)
        return len(self.points)
        
    def write_kmp_enph(self, f, index):
         f.write(pack(">B", index ) ) 
         f.write(pack(">B", len(self.points) ) ) 
         f.write(pack(">bbbbbb", self.prev[0], self.prev[1], self.prev[2], self.prev[3], self.prev[4], self.prev[5]) )
         f.write(pack(">bbbbbb", self.next[0], self.next[1], self.next[2], self.next[3], self.next[4], self.next[5]) )
         f.write(pack(">H",  0) )

    def write_kmp_itpt(self, f):
        for point in self.points:
            point.write_kmp_itpt(f)
        
    def write_kmp_itph(self, f, index):
         #print(self.prev, self.next)
    
         f.write(pack(">B", index ) ) 
         f.write(pack(">B", len(self.points) ) ) 
         f.write(pack(">bbbbbb", self.prev[0], self.prev[1], self.prev[2], self.prev[3], self.prev[4], self.prev[5]) )
         f.write(pack(">bbbbbb", self.next[0], self.next[1], self.next[2], self.next[3], self.next[4], self.next[5]) )
         f.write(pack(">H",  0) )

class EnemyPointGroups(object):
    def __init__(self):
        self.groups = []
        self._group_ids = {}

    @classmethod
    def from_file(cls, f, count, old_bol=False):
        enemypointgroups = cls()
        curr_group = None

        for i in range(count):
            enemypoint = EnemyPoint.from_file(f, old_bol)
            print("Point", i, "in group", enemypoint.group, "links to", enemypoint.link)
            if enemypoint.group not in enemypointgroups._group_ids:
                # start of group
                curr_group = EnemyPointGroup()
                curr_group.id = enemypoint.group
                enemypointgroups._group_ids[enemypoint.group] = curr_group
                curr_group.points.append(enemypoint)
                enemypointgroups.groups.append(curr_group)
            else:
                enemypointgroups._group_ids[enemypoint.group].points.append(enemypoint)

        return enemypointgroups

    @classmethod
    def from_file_kmp(cls, f):
        enemypointgroups = cls()
        
        assert f.read(4) == b"ENPT"
        count = read_uint16(f)
        f.read(2)
        
        
        all_points = []
        #read the enemy points
        for i in range(count):
            enemypoint = EnemyPoint.from_file_kmp(f)
            all_points.append(enemypoint)
        
        assert f.read(4) == b"ENPH"
        count = read_uint16(f)
        f.read(2)
        
       
        for i in range(count):
            enemypath = EnemyPointGroup.from_file_kmp(f, i, all_points)
            enemypointgroups.groups.append(enemypath)

        
        #link logic
        link = 0
        to_visit = [0]
        hit = [0] * count
        
        while len(to_visit) > 0 and sum(hit) < count:
            
            curr_group = to_visit[0]
            
            if hit[curr_group] == 0:
                
                hit[curr_group] = 1
                enemypointgroups.groups[curr_group].points[-1].link = link
                
                #make the other inputs have the same link
                for idx, group in enumerate( enemypointgroups.groups ):
                    
                    if  len( list( set(group.next) & set(enemypointgroups.groups[curr_group].next)  ) ) > 0:
                        
                        group.points[-1].link = link
                        hit[idx] = 1
                #make the outputs have the same link
                for group_idx in enemypointgroups.groups[curr_group].next:
                    
                    enemypointgroups.groups[group_idx].points[0].link = link
                    to_visit.append(group_idx)

                link += 1
            to_visit.pop(0)

            
        


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
                
            

    def write_kmp(self, f):
        self.assign_prev_next()
    
        f.write(b"ENPT")
        count_offset = f.tell() 
        f.write(pack(">H", 0) ) # will be overridden later
        f.write(pack(">H", 0) )
        
        sum_points = 0
        point_indices = []
        
        for group in self.groups:
            point_indices.append(sum_points)
            sum_points += group.write_kmp_points_enpt(f)        
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
            group.write_kmp_enph(f, point_indices[idx])

        itpt_offset = f.tell()
        f.write(b"ITPT")
        
        count_offset = f.tell()
        f.write(pack(">H", sum_points) )
        f.write(pack(">H", 0) )
        for group in self.groups:
            group.write_kmp_itpt(f)
        
        itph_offset = f.tell()
        
        f.write(b"ITPH")
        f.write(pack(">H", len(self.groups) ) ) 
        f.write(pack(">H", 0) )
        
        for idx, group in enumerate( self.groups ):
            group.write_kmp_itph(f, point_indices[idx])
        
        return enph_offset, itpt_offset, itph_offset

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

    @classmethod
    def from_file_kmp(cls, f, all_points):
    
        checkpointgroup = cls.new()
    
        start_point = read_uint8(f)
        end_point = read_uint8(f)
        print( start_point, end_point, len(all_points))
        assert( all_points[start_point].prev == 0xFF )
        assert( all_points[start_point + end_point - 1].next == 0xFF)
        checkpointgroup.points = all_points[start_point: start_point + end_point - 1]
        
        checkpointgroup.prevgroup = unpack(">bbbbbb", f.read(6))
        checkpointgroup.nextgroup = unpack(">bbbbbb", f.read(6))
        f.read(2)
        
        return checkpointgroup
        
    
    def write(self, f):
        self._pointcount = len(self.points)

        f.write(pack(">HH", self._pointcount, self.grouplink))
        f.write(pack(">hhhh", *self.prevgroup[0:4]))
        f.write(pack(">hhhh", *self.nextgroup[0:4]))

    def write_kmp_ckpt(self, f, key):
        
        key = self.points[0].write_kmp(f, -1, 1, key)
        for i in range(1, len( self.points) -1 ):
            key = self.points[i].write_kmp(f, i-1, i + 1, key)
        key = self.points[-1].write_kmp(f, len(self.points) - 2, -1, key)
        return len(self.points), key
        
    def write_kmp_ckph(self, f, index):
         f.write(pack(">B", index ) ) 
         f.write(pack(">B", len(self.points) ) ) 
         f.write(pack(">bbbbBB", self.prevgroup[0], self.prevgroup[1], self.prevgroup[2], self.prevgroup[3], 0xFF, 0xFF) )
         f.write(pack(">bbbbBB", self.nextgroup[0], self.nextgroup[1], self.nextgroup[2], self.nextgroup[3], 0xFF, 0xFF) )
         f.write(pack(">H",  0) )

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
        #print(start, end)
        assert unk4 == 0
        assert unk2 == 0 or unk2 == 1
        assert unk3 == 0 or unk3 == 1
        return cls(start, end, unk1, unk2, unk3, unk4)

    @classmethod
    def from_file_kmp(cls, f):
        checkpoint = cls.new()
        
        checkpoint.start = Vector3(*unpack(">f", f.read(4) ), 0, *unpack(">f", f.read(4) ) )
        checkpoint.end = Vector3(*unpack(">f", f.read(4) ), 0, *unpack(">f", f.read(4) ) )
        checkpoint.unk1 = read_uint8(f)
        
        checkpoint_type = read_uint8(f)
        if checkpoint_type == 0xFF:
            checkpoint.unk2 = 0
        else:
            checkpoint.unk2 = 1

        checkpoint.prev = read_uint8(f)
        checkpoint.next = read_uint8(f)
        
        return checkpoint

    def write(self, f):
        f.write(pack(">fff", self.start.x, self.start.y, self.start.z))
        f.write(pack(">fff", self.end.x, self.end.y, self.end.z))
        f.write(pack(">BBBB", self.unk1, self.unk2, self.unk3, self.unk4))

    def write_kmp(self, f, prev, next, key, lap_counter = False ):
        f.write(pack(">ff", self.start.x, self.start.z))
        f.write(pack(">ff", self.end.x, self.end.z))
        f.write(pack(">b", self.unk1))
        #print(key)
        if self.unk2 == 1:
            f.write(pack(">b", key))
            key += 1
        else:
            f.write(pack(">B", 0xFF))
        f.write(pack(">bb", prev, next) )
        return key

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

    @classmethod
    def from_file_kmp(cls, f):
        checkpointgroups = cls()
        
        assert f.read(4) == b"CKPT"
        count = read_uint16(f)
        f.read(2)
        
        all_points = []
        #read the enemy points
        for i in range(count):
            checkpoint = Checkpoint.from_file_kmp(f)
            all_points.append(checkpoint)
        
        
        assert f.read(4) == b"CKPH"
        count = read_uint16(f)
        f.read(2)
        
        for i in range(count):
            checkpointpath = CheckpointGroup.from_file_kmp(f, all_points)
            checkpointgroups.groups.append(checkpointpath)
        
        
        return checkpointgroups

    def new_group_id(self):
        return len(self.groups)

    def points(self):
        for group in self.groups:
            for point in group.points:
                yield point

    def write_kmp(self, f):
        f.write(b"CKPT")
        count_offset = f.tell()
        f.write(pack(">H", 0) ) # will be overridden later
        f.write(pack(">H", 0) )
        
        sum_points = 0
        indices_offset = []
        num_key = 0
        
        
        for group in self.groups:
            indices_offset.append(sum_points)
            idx_points, num_key = group.write_kmp_ckpt(f, num_key) 
            sum_points += idx_points
        ckph_offset = f.tell()

        if sum_points > 0xFF:
            raise Exception("too many checkpoints")
        else:
            f.seek(count_offset)
            f.write(pack(">H", sum_points) )
        
        f.seek(ckph_offset)
        f.write(b"CKPH")
        f.write(pack(">H", len(self.groups) ) ) 
        f.write(pack(">H", 0) )
        
        for idx, group in enumerate( self.groups ):
            group.write_kmp_ckph(f, indices_offset[idx])
        return ckph_offset
        
    
# Section 3
# Routes/Paths for cameras, objects and other things
class Route(object):
    def __init__(self):
        self.points = []
        self._pointcount = 0
        self._pointstart = 0
        self.unk1 = 0
        self.unk2 = 0

    @classmethod
    def new(cls):
        return cls()


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
        assert pad == b"\x00"*7

        return route

    @classmethod
    def from_file_kmp(cls, f):
        route = cls()
        route._pointcount = read_uint16(f)
        route.unk1 = read_uint8(f)
        route.unk2 = read_uint8(f)
        
        for i in range(route._pointcount):
            route.points.append( RoutePoint.from_file_kmp(f)  )
        
        
        return route


    def add_routepoints(self, points):
        for i in range(self._pointcount):
            self.points.append(points[self._pointstart+i])

    def write(self, f, pointstart):
        f.write(pack(">HH", len(self.points), pointstart))
        f.write(pack(">IB", self.unk1, self.unk2))
        f.write(b"\x00"*7)

    def write_kmp(self, f):
         f.write(pack(">H", len(self.points) ) )
         
         if len(self.points) <= 2:
            f.write(pack(">B", 0 ) )
         else:
            f.write(pack(">B", self.unk1 & 0xFF ) )
         
         f.write(pack(">B", self.unk2) )
         
         for point in self.points:
            point.write_kmp(f)
         return len(self.points)

# Section 4
# Route point for use with routes from section 3
class RoutePoint(object):
    def __init__(self, position):
        self.position = position
        self.unk = 0
        self.unk2 = 0

    @classmethod
    def new(cls):
        return cls(Vector3(0.0, 0.0, 0.0))


    @classmethod
    def from_file(cls, f):
        position = Vector3(*unpack(">fff", f.read(12)))
        point = cls(position)

        point.unk = read_uint32(f)

        padding = f.read(16)
        assert padding == b"\x00"*16
        return point

    @classmethod
    def from_file_kmp(cls, f):
        position = Vector3(*unpack(">fff", f.read(12)))
        point = cls(position) 
        
        point.unk = read_uint16(f)
        point.unk2 = read_uint16(f)
        
        return point
        


    def write(self, f):
        f.write(pack(">fffI", self.position.x, self.position.y, self.position.z,
                     self.unk))
        f.write(b"\x00"*16)

    def write_kmp(self, f):
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z ) )
        f.write(pack(">HH", self.unk & 0xFFFF, 0) )
# Section 5
# Objects
class MapObject(object):
    def __init__(self, position, objectid):
        self.position = position
        self.scale = Vector3(1.0, 1.0, 1.0)
        self.rotation = Rotation.default()
        self.objectid = objectid
        self.pathid = -1
        self.unk_28 = 0
        self.unk_2a = 0
        self.presence_filter = 255
        self.presence = 0x3
        self.unk_flag = 0
        self.unk_2f = 0
        self.userdata = [0 for i in range(8)]

        self.widget = None

    @classmethod
    def new(cls):
        return cls(Vector3(0.0, 0.0, 0.0), 1)

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
        obj.pathid = read_int16(f)
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

    @classmethod 
    def from_file_kmp(cls, f, bol2kmp):
        object = cls.new()
        
        obj_id = read_uint16(f)
        for key, value in bol2kmp.items(): 
            if isinstance(value, str) and int(value) == obj_id:
                object.objectid = int(key)
            else:
                object.object_id = 0
                object.unk_28 = obj_id
                object.unk_2f = 1
                
        f.read(2)
        object.position = Vector3(*unpack(">fff", f.read(12)))
        rotation = Vector3(*unpack(">fff", f.read(12)))
        #print(rotation)
        object.rotation = Rotation.from_euler(rotation)
        
        object.scale = Vector3(*unpack(">fff", f.read(12)))
        object.route = read_uint16(f)
        object.settings = unpack(">hhhhhhhh", f.read(2 * 8))
        object.presence = read_uint16(f)
        if object.presence == 6:
            object.presence == 2
        elif object.presence == 7:
            object.presence == 3
        
        
        
        return object

    def write(self, f):
        start = f.tell()
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        f.write(pack(">fff", self.scale.x, self.scale.y, self.scale.z))
        self.rotation.write(f)

        f.write(pack(">hhHh", self.objectid, self.pathid, self.unk_28, self.unk_2a))
        f.write(pack(">BBBB", self.presence_filter, self.presence, self.unk_flag, self.unk_2f))

        for i in range(8):
            f.write(pack(">h", self.userdata[i]))
        #assert f.tell() - start == self._size
    def write_kmp(self, f, options):
        if self.presence == 0:
            return 0
        
        if options is None:
            if self.unk_28 != 0:
                f.write(pack(">H", self.unk_28) )
            else:
                return 0
        else:
            if type(options) is dict:
                idx = 0
                if options["offset"] == "col" and self.unk_flag == 1:
                    idx = 1
                elif options["offset"] == "rou" and self.pathid == -1:
                    idx = -1
                elif options["unk_28"]:
                    idx = self.unk_28
                f.write(pack(">H", int(options["variants"][idx] )  ))
            else:
                f.write(pack(">H", int(options)  ))
        
        
        f.write(pack(">H", 0) )
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        ang = self.rotation.get_euler()
        
        f.write(pack(">fff", ang[0], ang[1] + 90, ang[2]))
        f.write(pack(">fff", self.scale.x, self.scale.y, self.scale.z))
        f.write(pack(">h", self.pathid) )
        
        if self.objectid == 1:
            for i in range(8):
                f.write(pack(">h", 0))
        else:
            for i in range(8):
                f.write(pack(">h", self.userdata[i]))
        
        if self.presence == 1:
            f.write( pack(">H", 1) )
        elif self.presence == 2:
            f.write( pack(">H", 6) )
        elif self.presence == 3:
            f.write( pack(">H", 7) )
        
        return 1

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
        
    @classmethod
    def from_file_kmp(cls, f, objectcount):
        mapobjs = cls()
        
        with open ("kmpobjects.json") as g:
            bol2kmp = json.load(g)

        for i in range(objectcount):
            obj = MapObject.from_file_kmp(f, bol2kmp)
            mapobjs.objects.append(obj)

        return mapobjs
    
    def write_kmp(self, f):
    
        num_written = 0
    
        with open ("kmpobjects.json") as g:
            bol2kmp = json.load(g)
        
        f.write(b"GOBJ")
        count_offset = f.tell()
        f.write(pack(">H", len(self.objects)))
        f.write(pack(">H", 0) )
            
        #print(bol2kmp)
        for object in self.objects:
            if str(object.objectid) in bol2kmp:            
                num_written += object.write_kmp(f, bol2kmp[str(object.objectid)])
            else:
                num_written += object.write_kmp(f, None )
        end_sec = f.tell()
        f.seek(count_offset)
        f.write(pack(">H", num_written))
        f.seek(end_sec)

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

    @classmethod
    def from_file_kmp(cls, f):
        position = Vector3(*unpack(">fff", f.read(12)))

        kstart = cls(position)
        rotation = Vector3(*unpack(">fff", f.read(12)))
        #print(rotation)
        kstart.rotation = Rotation.from_euler(rotation)
        kstart.playerid = read_uint16(f) & 0xFF
        kstart.unknown = read_uint16(f)
        return kstart


    def write(self, f):
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        f.write(pack(">fff", self.scale.x, self.scale.y, self.scale.z))
        self.rotation.write(f)
        f.write(pack(">BBH", self.poleposition, self.playerid, self.unknown))
    def write_kmp(self,f):
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        
        ang = self.rotation.get_euler()
        #print(ang)
        f.write(pack(">fff", ang[0], ang[1] + 90, ang[2]))
        
        if self.playerid == 0xFF:
            f.write(pack(">H", self.playerid + 0xFF00 ) )
        else:
            f.write(pack(">H", self.playerid ) )
        f.write(pack(">H",  0) )

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
    @classmethod
    def from_file_kmp(cls, f, count):
        kspoints = cls()
        for i in range(count):
            kstart = KartStartPoint.from_file_kmp(f)
            kspoints.positions.append(kstart)
        
        return kspoints
    
    def write_kmp(self, f):
        f.write(b"KTPT")
        f.write(pack(">H", len(self.positions)))
        f.write(pack(">H", 0) )
        for position in self.positions:
            position.write_kmp(f)

# Section 7
# Areas
class Area(object):
    def __init__(self, position):
        self.position = position
        self.scale = Vector3(1.0, 1.0, 1.0)
        self.rotation = Rotation.default()
        self.check_flag = 0
        self.area_type = 0
        self.camera_index = -1
        self.unk1 = 0
        self.unk2 = 0
        self.unkfixedpoint = 0
        self.unkshort = 0
        self.shadow_id = 0
        self.lightparam_index = 0

    @classmethod
    def new(cls):
        return cls(Vector3(0.0, 0.0, 0.0))

    @classmethod
    def from_file(cls, f):
        position = Vector3(*unpack(">fff", f.read(12)))

        area = cls(position)
        area.scale = Vector3(*unpack(">fff", f.read(12)))
        area.rotation = Rotation.from_file(f)
        area.check_flag = read_uint8(f)
        area.area_type = read_uint8(f)
        area.camera_index = read_int16(f)
        area.unk1 = read_uint32(f)
        area.unk2 = read_uint32(f)
        area.unkfixedpoint = read_int16(f)
        area.unkshort = read_int16(f)
        area.shadow_id = read_int16(f)
        area.lightparam_index = read_int16(f)

        return area

    @classmethod
    def from_file_kmp(cls, f):
        unk1 = read_uint8(f)
        type = read_uint8(f)
        camera = read_uint8(f)
        unk2 = read_uint8(f)

        if type < 2:
            type = type - 1
    
        position = Vector3(*unpack(">fff", f.read(12)))
        area = cls(position)
        area.unk1 = unk1;
        area.type = type
        area.camera = camera
        area.unk2 = unk2
        
        rotation = Vector3(*unpack(">fff", f.read(12)))
        #print(rotation)
        area.rotation = Rotation.from_euler(rotation)
        
        
        area.scale = Vector3(*unpack(">fff", f.read(12)))
        area.scale.x = area.scale.x * 100
        area.scale.y = area.scale.y * 100
        area.scale.z = area.scale.z * 100

        area.unkfixedpoint = read_int16(f)
        area.unkshort = read_int16(f)
        area.shadow_id = read_uint8(f)
        area.lightparam_index = read_uint8(f)

        f.read(2)

        return area


    def write(self, f):
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        f.write(pack(">fff", self.scale.x, self.scale.y, self.scale.z))
        self.rotation.write(f)
        f.write(pack(">BBh", self.check_flag, self.area_type, self.camera_index))
        f.write(pack(">II", self.unk1, self.unk2))
        f.write(pack(">hhhh", self.unkfixedpoint, self.unkshort, self.shadow_id, self.lightparam_index))
    def write_kmp(self, f):
        good_areas = [1, 2, 5]
        if not self.area_type in good_areas:
            return 0
        if self.area_type == 5 and self.camera_index == -1:
            return 0
        
        f.write(pack(">B", self.unk1 & 0xFF) )
        
        if self.area_type == 5:
            f.write(pack(">B", 0) )
        else:
            f.write(pack(">B", self.area_type - 1) )
        
        if self.area_type == 0x1:
            f.write(pack(">b", self.camera_index) )
        else:  
            f.write(pack(">b", -1) )
        f.write(pack(">B", self.unk2 & 0xFF) )
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        ang = self.rotation.get_euler()
        f.write(pack(">fff", ang[0], ang[1] + 90, ang[2]))
        f.write(pack(">fff", self.scale.x/100, self.scale.y/100, self.scale.z/100))
        f.write(pack(">HHBBH", 0, 0, 0, 0, 0 ) )
       
        return 1

class Areas(object):
    def __init__(self):
        self.areas = []

    @classmethod
    def from_file(cls, f, count):
        areas = cls()
        for i in range(count):
            areas.areas.append(Area.from_file(f))

        return areas

    @classmethod 
    def from_file_kmp(cls, f, count):
        areas = cls()
        for i in range(count):
            new_area = Area.from_file_kmp(f)
            if new_area is not None:
                areas.areas.append(new_area)

        return areas

    def write_kmp(self, f):
        f.write(b"AREA")
        area_count_off = f.tell()
        f.write(pack(">H", 0xFFFF) )
        f.write(pack(">H", 0) )
        
        num_written = 0
        for area in self.areas:
            num_written += area.write_kmp(f)
            
        end_sec = f.tell()
        f.seek(area_count_off)
        f.write(pack(">H", num_written) )
        f.seek(end_sec)
# Section 8
# Cameras
class Camera(object):
    def __init__(self, position):
        self.position = position
        self.position2 = Vector3(0.0, 0.0, 0.0)
        self.position3 = Vector3(0.0, 0.0, 0.0)
        self.rotation = Rotation.default()

        self.unkbyte = 0
        self.camtype = 0
        self.startzoom = 0
        self.camduration = 0
        self.startcamera = 0
        self.unk2 = 0
        self.unk3 = 0
        self.route = -1
        self.routespeed = 0
        self.endzoom = 0
        self.nextcam = -1
        self.name = "null"

    @classmethod
    def new(cls):
        return cls(Vector3(0.0, 0.0, 0.0))

    @classmethod
    def from_file(cls, f):
        start = f.tell()
        hexd = f.read(4*3*4)
        f.seek(start)
        print(hexlify(hexd))

        position = Vector3(*unpack(">fff", f.read(12)))

        cam = cls(position)
        cam.rotation = Rotation.from_file(f)
        cam.position2 = Vector3(*unpack(">fff", f.read(12)))
        cam.position3 = Vector3(*unpack(">fff", f.read(12)))
        cam.unkbyte = read_uint8(f) #shake?
        cam.camtype = read_uint8(f)
        cam.startzoom = read_uint16(f)
        cam.camduration = read_uint16(f)
        cam.startcamera = read_uint16(f)
        cam.unk2 = read_uint16(f)
        cam.unk3 = read_uint16(f)
        cam.route = read_int16(f)
        cam.routespeed = read_uint16(f)
        cam.endzoom = read_uint16(f)
        cam.nextcam = read_int16(f)
        cam.name = str(f.read(4), encoding="ascii")

        return cam

    @classmethod
    def from_file_kmp(cls, f):
        type = read_uint8(f)
        if type == 0:
            position = Vector3(-860.444, 6545.688, 3131.74)
            cam = cls(position)
            
            cam.rotation = Rotation.from_euler(Vector3(0, 0, 0))
            cam.position2 = Vector3(160, 6, 0)
            cam.position3 = Vector3(-20, -20, 450)
            cam.unkbyte = 0
            cam.camtype = 8
            cam.startzoom = 85
            cam.camduration = 1800
            cam.startcamera = 0
            cam.unk2 = 0
            cam.unk3 = 0
            cam.route = -1
            cam.route_speed = 1
            cam.endzoom = 5
            cam.next_cam = -1
            cam.name = "para"
            
            
            f.read(0x47)
            
            return cam
            
        else:
            if type == 1:
                type = 0
            elif type == 2:
                type = 1
            elif type == 3:
                type = 7
        
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
            cam.unkbyte = shake
            cam.route = route
            cam.routespeed = move_velocity
            
            
            
            rotation = Vector3(*unpack(">fff", f.read(12)))
            #print(rotation)
            cam.rotation = Rotation.from_euler(rotation)
            
            cam.startzoom = read_float(f)
            cam.endzoom = read_float(f)
            cam.position3 = Vector3(*unpack(">fff", f.read(12)))
            cam.position2 = Vector3(*unpack(">fff", f.read(12)))
            cam.camduration = read_float(f)
            cam.name = "mkwi"
            
            return cam
            
    #write to bol
    def write(self, f):
    
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        self.rotation.write(f)
        f.write(pack(">fff", self.position2.x, self.position2.y, self.position2.z))
        f.write(pack(">fff", self.position3.x, self.position3.y, self.position3.z))
    
        if self.name == "null" or self.name == "para":
    
            
            f.write(pack(">BBHHH", self.unkbyte, self.camtype, int(self.startzoom), int(self.camduration), self.startcamera))
            f.write(pack(">HHhHHh",
                         self.unk2, self.unk3, self.route,
                         self.routespeed, int(self.endzoom), self.nextcam))
        else:
            f.write(pack(">BBHHH", self.unkbyte, self.camtype, int(self.startzoom), int(self.camduration), self.startcamera))
            f.write(pack(">HHhHHh",
                         self.unk2, self.unk3, self.route,
                         int(self.routespeed / 10), int(self.endzoom), self.nextcam))
        
        assert len(self.name) == 4    
        if self.name == "para":
            f.write(bytes(self.name, encoding="ascii"))
        else:
            f.write(bytes("null", encoding="ascii"))

    def write_kmp(self, f):
        
    
    
        if self.camtype == 0:
            f.write(pack(">B", 1 ) )
        elif self.camtype == 1:
            f.write(pack(">B", 2 ) )
        elif self.camtype == 4:
            f.write(pack(">B", 4 ) )
        elif self.camtype == 5 or self.camtype == 6:
            f.write(pack(">B", 5 ) )
        elif self.camtype == 7:
            f.write(pack(">B", 3 ) )
        elif self.camtype == 8:
            
            f.write(pack(">B", 0 ) )
        else:
            return 0
            
        if self.camtype == 8:
           f.write(pack(">bBb", -1, 0, -1) )
           f.write(pack(">H", 0x0000 ) )
           f.write(pack(">H", 0x001E ) )
           f.write(pack(">I", 0x0) )
           
        else:
           
            f.write(pack(">bBb", self.nextcam, 0, self.route) )
            f.write(pack(">H", self.routespeed * 100 ) )
            if self.camduration == 0:
                f.write(pack(">H", 0 ) )
            else:
                f.write(pack(">H",  int( (self.startzoom - self.endzoom) / self.camduration ) ) )
            
            diff = (self.position2 - self.position3).norm() * self.camduration
            
            
            if self.camduration == 0:
                f.write(pack(">H",  0) )
            else:
                f.write(pack(">H", int( diff / self.camduration)  ))
            f.write(pack(">BB", self.unk2 & 0xFF, self.unk3 & 0xFF ) )
       
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))       
        f.write(pack(">fff", 0, 0, 0))
        
        if self.camtype == 8:
             f.write(pack(">ff", 85, 40) )
             f.write(pack(">fff", 30, -1, 550) )
             f.write(pack(">fff", 5, 1, 0) )
             f.write(pack(">f", 0) )
             
             
        
        else:
        
            f.write(pack(">ff", self.startzoom, self.endzoom))
            
            
            f.write(pack(">fff", self.position3.x, self.position3.y, self.position3.z))  
            if self.camtype == 6:      
                f.write(pack(">fff", self.position3.x, self.position3.y, self.position3.z)) 
            else:
                f.write(pack(">fff", self.position2.x, self.position2.y, self.position2.z))   
            f.write(pack(">f", self.camduration) )
            
        return 1

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

    @classmethod
    def new(cls):
        return cls(Vector3(0.0, 0.0, 0.0))

    @classmethod
    def from_file(cls, f):
        position = Vector3(*unpack(">fff", f.read(12)))
        jugem = cls(position)
        jugem.rotation = Rotation.from_file(f)
        jugem.respawn_id = read_uint16(f)
        jugem.unk1 = read_uint16(f)
        jugem.unk2 = read_int16(f)
        jugem.unk3 = read_int16(f)

        return jugem

    @classmethod
    def from_file_kmp(cls, f):
        position = Vector3(*unpack(">fff", f.read(12)))
        jugem = cls(position)
        
        rotation = Vector3(*unpack(">fff", f.read(12)))
        #print(rotation)
        jugem.rotation = Rotation.from_euler(rotation)
        
        jugem.respawn_id = read_uint16(f)
        jugem.unk2 = read_int16(f)

        return jugem


    def write(self, f):
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        self.rotation.write(f)
        f.write(pack(">HHhh", self.respawn_id, self.unk1, self.unk2, self.unk3))
    def write_kmp_jgpt(self, f, count):
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        ang = self.rotation.get_euler()
        f.write(pack(">fff", ang[0], ang[1] + 90, ang[2]))
        f.write(pack(">H", count) )
        f.write(pack(">h", -1 ) )
        
    def write_kmp_cngpt(self, f, count):
        f.write(pack(">fff", self.position.x, self.position.y, self.position.z))
        ang = self.rotation.get_euler()
        f.write(pack(">fff", ang[0], ang[1] + 90, ang[2]))
        f.write(pack(">Hh", count, self.unk3 & 0xFF) )

# Section 10
# LightParam
class LightParam(object):
    def __init__(self):
        self.color1 = ColorRGBA(0x64, 0x64, 0x64, 0xFF)
        self.color2 = ColorRGBA(0x64, 0x64, 0x64, 0x00)
        self.unkvec = Vector3(0.0, 0.0, 0.0)



    @classmethod
    def new(cls):
        return cls()

    @classmethod
    def from_file(cls, f):
        lp = cls()
        lp.color1 = ColorRGBA.from_file(f)
        lp.unkvec = Vector3(*unpack(">fff", f.read(12)))
        lp.color2 = ColorRGBA.from_file(f)

        return lp

    def write(self, f):
        self.color1.write(f)
        f.write(pack(">fff", self.unkvec.x, self.unkvec.y, self.unkvec.z))
        self.color2.write(f)


# Section 11
# MG (MiniGame?)
class MGEntry(object):
    def __init__(self):
        self.unk1 = 0
        self.unk2 = 0
        self.unk3 = 0
        self.unk4 = 0

    @classmethod
    def new(cls):
        return cls(0)

    @classmethod
    def from_file(cls, f):
        mgentry = MGEntry()
        mgentry.unk1 = read_int16(f)
        mgentry.unk2 = read_int16(f)
        mgentry.unk3 = read_int16(f)
        mgentry.unk4 = read_int16(f)

        return mgentry

    def write(self, f):
        f.write(pack(">hhhh", self.unk1, self.unk2, self.unk3, self.unk4))


class BOL(object):
    def __init__(self):
        self.roll = 0
        self.rgb_ambient = ColorRGB(0x64, 0x64, 0x64)
        self.rgba_light = ColorRGBA(0xFF, 0xFF, 0xFF, 0xFF)
        self.lightsource = Vector3(0.0, 0.0, 0.0)
        self.fog_type = 0
        self.fog_color = ColorRGB(0x64, 0x64, 0x64)
        self.fog_startz = 8000.0
        self.fog_endz = 230000.0
        self.unk1 = 0
        self.unk2 = 0
        self.unk3 = 0
        self.starting_point_count = 0
        self.unk5 = 0
        self.unk6 = 0

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
        self.respawnpoints = ObjectContainer()
        self.lightparams = ObjectContainer()
        self.mgentries = ObjectContainer()

    def objects_with_position(self):
        for group in self.enemypointgroups.groups.values():
            for point in group.points:
                yield point

        for route in self.routes:
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


    @classmethod
    def from_file(cls, f):
        bol = cls()
        magic = f.read(4)
        print(magic, type(magic))
        assert magic == b"0015" or magic == b"0012"
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
        bol.unk1 = read_uint16(f)
        bol.unk2 = read_uint8(f)
        bol.unk3 = read_uint8(f)
        bol.shadow_color = ColorRGB.from_file(f)
        bol.starting_point_count = read_uint8(f)
        bol.unk5 = read_uint8(f)

        sectioncounts[LIGHTPARAM] = read_uint8(f)
        sectioncounts[MINIGAME] = read_uint8(f)
        bol.unk6 = read_uint8(f)

        filestart = read_uint32(f)
        print(hex(f.tell()), filestart)
        assert filestart == 0

        sectionoffsets = {}
        for i in range(11):
            sectionoffsets[i+1] = read_uint32(f)

        padding = f.read(12) # padding
        assert padding == b"\x00"*12
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
        assert len(bol.kartpoints.positions) == bol.starting_point_count

        f.seek(sectionoffsets[AREA])
        bol.areas = Areas.from_file(f, sectioncounts[AREA])

        f.seek(sectionoffsets[CAMERA])
        bol.cameras = ObjectContainer.from_file(f, sectioncounts[CAMERA], Camera)

        f.seek(sectionoffsets[RESPAWNPOINT])
        bol.respawnpoints = ObjectContainer.from_file(f, sectioncounts[RESPAWNPOINT], JugemPoint)

        f.seek(sectionoffsets[LIGHTPARAM])

        bol.lightparams = ObjectContainer.from_file(f, sectioncounts[LIGHTPARAM], LightParam)

        f.seek(sectionoffsets[MINIGAME])
        bol.mgentries = ObjectContainer.from_file(f, sectioncounts[MINIGAME], MGEntry)

        return bol

    @classmethod
    def from_file_kmp(cls, f):
        bol = cls()
        magic = f.read(4)
        assert magic == b"RKMD"
        
        bol.unk4 = 1
        
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
        bol.kartpoints = KartStartPoints.from_file_kmp(f, count)
        
        f.seek(enpt_offset + header_len)
        bol.enemypointgroups = EnemyPointGroups.from_file_kmp(f)
        
        #skip itpt
        f.seek(ckpt_offset + header_len)
        bol.checkpoints = CheckpointGroups.from_file_kmp(f)
        
        #bol.checkpoints = CheckpointGroups.from_file_kmp(f, sectioncounts[CHECKPOINT])
        
        f.seek(gobj_offset + header_len)
        assert f.read(4) == b"GOBJ"
        count = read_uint16(f)
        f.read(2)
        bol.objects = MapObjects.from_file_kmp(f, count)
        
        f.seek(poti_offset + header_len)
        assert f.read(4) == b"POTI"
        count = read_uint16(f)
        total = read_uint16(f)
        
        # will handle the routes
        bol.routes = ObjectContainer.from_file_kmp(f, count, Route)


        f.seek(area_offset + header_len)
        assert f.read(4) == b"AREA"
        count = read_uint16(f)
        f.read(2)
        bol.areas = Areas.from_file_kmp(f, count)
        
        f.seek(came_offset + header_len)
        assert f.read(4) == b"CAME"
        count = read_uint16(f)
        start = read_uint8(f)
        print(start)
        f.read(1)
        bol.cameras = ObjectContainer.from_file_kmp(f, count, Camera)
        bol.cameras[start].startcamera = 1
        
        f.seek(jgpt_offset + header_len)
        assert f.read(4) == b"JGPT"
        count = read_uint16(f)
        f.read(2)
        bol.respawnpoints = ObjectContainer.from_file_kmp(f, count, JugemPoint)
        
        f.seek(cnpt_offset + header_len)
        assert f.read(4) == b"CNPT"
        count = read_uint16(f)
        f.read(2)
        for i in range(count):
            bol.respawnpoints.append( JugemPoint.from_file_kmp(f)  )

        f.seek(stgi_offset + header_len)
        assert f.read(4) == b"STGI"
        f.read(2)
        f.read(2)
        bol.lap_count = read_uint8(f)
        bol.kartpoints.positions[0].poleposition = read_uint8(f)
        
        
        bol.lightparams = ObjectContainer()
        bol.lightparams.append(LightParam.new())
        
        bol.shadow_color = ColorRGB(0, 0, 0)

        return bol

    def write(self, f):
        f.write(b"0015")
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
        write_uint16(f, len(self.routes))
        write_uint16(f, len(self.respawnpoints))

        f.write(pack(">B", self.fog_type))
        self.fog_color.write(f)
        f.write(pack(">ffHBB",
                self.fog_startz, self.fog_endz,
                self.unk1, self.unk2, self.unk3))
        self.shadow_color.write(f)
        f.write(pack(">BB", len(self.kartpoints.positions), self.unk5))
        f.write(pack(">BB", len(self.lightparams), len(self.mgentries)))
        f.write(pack(">B", self.unk6))

        f.write(b"\x00"*4) # Filestart 0

        offset_start = f.tell()
        offsets = []
        for i in range(11):
            f.write(b"FOOB") # placeholder for offsets
        f.write(b"\x00"*12) # padding

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

        index = 0
        for route in self.routes:
            route.write(f, index)
            index += len(route.points)

        offsets.append(f.tell())
        for route in self.routes:
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
        for camera in self.cameras:
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
        print(len(offsets))
        assert len(offsets) == 11
        f.seek(offset_start)
        for offset in offsets:
            f.write(pack(">I", offset))


    def write_kmp(self, f):
         f.write(b"RKMD") #file magic
         size_off = f.tell()
         f.write(b"FFFF") #will be the length of the file
         f.write(pack(">H", 0xF)) #number of sections
         f.write(pack(">H", 0x4c)) #length of header
         f.write(pack(">I", 0x9d8)) #length of header
         sec_offs = f.tell()
         f.write(b"FFFF" * 15) #placeholder for offsets
         
         offsets = [ f.tell()] 
         
         self.kartpoints.write_kmp(f)
         
         offsets.append( f.tell() )
         enph_off, itpt_off, itph_off = self.enemypointgroups.write_kmp(f)
         offsets.append(enph_off)
         offsets.append(itpt_off)
         offsets.append(itph_off)
         
         offsets.append(f.tell())
         ktph_offset = self.checkpoints.write_kmp(f)
         offsets.append(ktph_offset)
         
         offsets.append(f.tell() )
         self.objects.write_kmp(f)
         
         offsets.append(f.tell() )
         f.write(b"POTI")       
         f.write(pack(">H", len(self.routes) ) )
         count_off = f.tell()   
         f.write(pack(">H", 0xFFFF ) )  # will be overridden later
         
         count = 0
         for route in self.routes:
            count += route.write_kmp(f)
         
         offset = f.tell()
         offsets.append(offset)
         
         f.seek(count_off)
         f.write(pack(">H", count ) )  # will be overridden later
         f.seek(offset)
         
         
         self.areas.write_kmp(f)
         offsets.append(f.tell() )
         f.write(b"CAME")
         count_off = f.tell()
         f.write(pack(">H", 0xFFFF ) )  # will be overridden later
         f.write(pack(">H", 0xFFFF ) )  # will be overridden later
         
         count = 0
         
         for camera in self.cameras:
            count += camera.write_kmp(f)
         
         starting_cam = 0
         for idx in range(len(self.cameras)):
            if self.cameras[idx].startcamera == 1:
                starting_cam = idx
                continue
         
         offset = f.tell()
         offsets.append(offset)
         
         f.seek(count_off)
         f.write(pack(">H", count ) )  # will be overridden later
         f.write(pack(">BB", starting_cam, 0 ) )
         f.seek(offset)
         
         f.write(b"JGPT")
         count_off = f.tell() 
         f.write(pack(">H", 0xFFFF ) )  # will be overridden later
         f.write(pack(">H", 0 ) )
         
         count = 0
         for point in self.respawnpoints:
            if point.unk2 != 1:
                
                point.write_kmp_jgpt(f, count)
                count += 1
         
         offset = f.tell()
         offsets.append(offset)
         
         f.seek(count_off)
         f.write(pack(">H", count ) )  # will be overridden later
         f.seek(offset)
         
         f.write(b"CNPT")
         count_off = f.tell() 
         f.write(pack(">H", 0xFFFF ) )  # will be overridden later
         f.write(pack(">H", 0 ) )
         
         count = 0
         for point in self.respawnpoints:
            if point.unk2 == 1:
                
                point.write_kmp_cnpt(f, count)
                count += 1
         offset = f.tell()
         offsets.append(offset)
         
         f.seek(count_off)
         f.write(pack(">H", count ) )  # will be overridden later
         f.seek(offset)
         
         f.write(b"MSPT")
         f.write(pack(">HH", 0, 0 ) )
         
         offsets.append(f.tell())
         f.write(b"STGI")
         f.write(pack(">HH", 1, 0 ) )
         f.write(pack(">BBBB", self.lap_count, self.kartpoints.positions[0].poleposition, 0, 1))
         f.write(pack(">BBBBB", 0, 0xFF, 0xFF, 0xFF, 0x4B ) )
         f.write(pack(">Hb", 0, 0 ) )
         
         assert( len(offsets) == 15 )
         size = f.tell()
         f.seek(size_off)
         f.write(pack(">I", size ) )
         f.seek(sec_offs)
         for i in range(15):
            f.write(pack(">I", offsets[i]  - 0x4C ) )
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