import math
from .vectors import Vector3, Triangle
from configuration import read_config

def collides(face_v1, face_v2, face_v3, box_mid_x, box_mid_z, box_size_x, box_size_z):
    half_x = box_size_x / 2.0
    min_x = min(face_v1.x, face_v2.x, face_v3.x) - box_mid_x
    if min_x > +half_x:
        return False
    max_x = max(face_v1.x, face_v2.x, face_v3.x) - box_mid_x
    if max_x < -half_x:
        return False

    half_z = box_size_z / 2.0
    min_z = min(face_v1.z, face_v2.z, face_v3.z) - box_mid_z
    if min_z > +half_z:
        return False
    max_z = max(face_v1.z, face_v2.z, face_v3.z) - box_mid_z
    if max_z < -half_z:
        return False

    return True


def subdivide_grid(minx, minz,
                   gridx_start, gridx_end, gridz_start, gridz_end,
                   cell_size, triangles, result):
    #print("Subdivision with", gridx_start, gridz_start, gridx_end, gridz_end, (gridx_start+gridx_end) // 2, (gridz_start+gridz_end) // 2)
    if gridx_start == gridx_end-1 and gridz_start == gridz_end-1:
        if gridx_start not in result:
            result[gridx_start] = {}
        result[gridx_start][gridz_start] = triangles

        return True

    # assert gridx_end > gridx_start or gridz_end > gridz_start

    halfx = (gridx_start+gridx_end) // 2
    halfz = (gridz_start+gridz_end) // 2

    # x->
    # 2 3 ^
    # 0 1 z
    coordinates = (
        (0, gridx_start , halfx     , gridz_start   , halfz),   # Quadrant 0
        (1, halfx       , gridx_end , gridz_start   , halfz),     # Quadrant 1
        (2, gridx_start , halfx     , halfz         , gridz_end),     # Quadrant 2
        (3, halfx       , gridx_end , halfz         , gridz_end) # Quadrant 3
    )
    skip = []
    if gridx_start == halfx:
        skip.append(0)
        skip.append(2)
    if halfx == gridx_end:
        skip.append(1)
        skip.append(3)
    if gridz_start == halfz:
        skip.append(0)
        skip.append(1)
    if halfz == gridz_end:
        skip.append(2)
        skip.append(3)


    coordinates = [([], startx, endx, startz, endz)
                   for quadrant_index, startx, endx, startz, endz in coordinates
                   if quadrant_index not in skip]

    for quadrant, startx, endx, startz, endz in coordinates:
        area_size_x = (endx - startx) * cell_size
        area_size_z = (endz - startz) * cell_size

        box_mid_x = minx + startx * cell_size + area_size_x // 2
        box_mid_z = minz + startz * cell_size + area_size_z // 2

        for triangle in triangles:
            _i, (v1, v2, v3, col_type) = triangle

            if collides(v1, v2, v3, box_mid_x, box_mid_z, area_size_x, area_size_z):
                quadrant.append(triangle)

    for quadrant, startx, endx, startz, endz in coordinates:
        subdivide_grid(minx, minz, startx, endx, startz, endz, cell_size, quadrant,
                       result)


def normalize_vector(v1):
    norm = v1.copy()
    norm.normalize()
    return norm



def create_vector(v1, v2):
    return v2 - v1


def cross_product(v1, v2):
    return v1.cross(v2)


MAX_X = 200000
MAX_Z = 200000



class Collision(object):
    def __init__(self, faces):
        self.faces = faces
        self.triangles = []
        #print(self.faces)
        for face in self.faces:
                
            v1, v2, v3 = face[0:3]
        
            col_type = 0x0100
            if len(face) > 3:
                col_type = face[3]

            #print(v1i, v2i, v3i, len(self.verts))
            v1 = Vector3(v1.x, -v1.z, v1.y)
            v2 = Vector3(v2.x, -v2.z, v2.y)
            v3 = Vector3(v3.x, -v3.z, v3.y)


            self.triangles.append(Triangle(v1,v2,v3,col_type))

        self.cell_size = 2000

        box_size_x = self.cell_size
        box_size_z = self.cell_size

        smallest_x =-MAX_X#max(-6000.0, smallest_x)
        smallest_z = -MAX_Z#max(-6000.0, smallest_z)
        biggest_x = MAX_X#min(6000.0, biggest_x)
        biggest_z = MAX_Z#min(6000.0, biggest_z)
        #print("dimensions are changed to", smallest_x, smallest_z, biggest_x, biggest_z)
        start_x = math.floor(smallest_x / box_size_x) * box_size_x
        start_z = math.floor(smallest_z / box_size_z) * box_size_z
        end_x = math.ceil(biggest_x / box_size_x) * box_size_x
        end_z = math.ceil(biggest_z / box_size_z) * box_size_z
        diff_x = abs(end_x - start_x)
        diff_z = abs(end_z - start_z)
        grid_size_x = int(diff_x // box_size_x)
        grid_size_z = int(diff_z // box_size_z)

        self.grid = {}
        triangles = [(i, face) for i, face in enumerate(faces)]
        subdivide_grid(start_x, start_z, 0, grid_size_x, 0, grid_size_z, self.cell_size, triangles, self.grid)
        print("finished generating triangles")
        #print(grid_size_x, grid_size_z)

        self.hidden_coltypes = set()
        self.hidden_colgroups = set()

    def collide_ray_downwards(self, x, z, y=99999999):
        grid_x = int((x+MAX_X) // self.cell_size)
        grid_z = int((z+MAX_Z) // self.cell_size)

        if grid_x not in self.grid or grid_z not in self.grid[grid_x]:
            return None

        triangles = self.grid[grid_x][grid_z]


        y = y
        dir_x = 0
        dir_y = -1.0
        dir_z = 0

        hit = None

        result = self._collide(triangles, x, y, z, -1.0)

        return result

    def collide_ray_closest(self, x, z, y):
        grid_x = int((x + MAX_X) // self.cell_size)
        grid_z = int((z + MAX_Z) // self.cell_size)

        if grid_x not in self.grid or grid_z not in self.grid[grid_x]:
            return None

        triangles = self.grid[grid_x][grid_z]


        y = y
        dir_x = 0
        dir_y = -1.0
        dir_z = 0

        hit = None

        result1 = self._collide(triangles, x, y, z, -1.0)
        result2 = self._collide(triangles, x, y, z, 1.0)

        if result1 is None and result2 is None:
            return None
        elif result1 is None:
            return result2
        elif result2 is None:
            return result1
        else:
            dist1 = abs(y - result1)
            dist2 = abs(y - result2)
            if dist1 > dist2:
                return result2
            else:
                return result1

    def _collide(self, triangles, x, y, z, dir_y):
        hit = None
        for i, face in triangles:#face in self.faces:#
            if isinstance(self.hidden_colgroups, str):
                self.hidden_colgroups = [int(x) for x in self.hidden_colgroups.split(",")]
            if isinstance(self.hidden_coltypes, str):
                self.hidden_coltypes = [int(x) for x in self.hidden_coltypes.split(",")]
            if len(face) > 3:
                if ( face[3] in self.hidden_coltypes) \
                    or ( face[3] & 0x1F in self.hidden_colgroups):
                    continue

            v1 = face[0]
            v2 = face[1]
            v3 = face[2]

            edge1 = create_vector(v1, v2)
            edge2 = create_vector(v1, v3)

            normal = cross_product(edge1, edge2)
            if normal.x == normal.y == normal.z == 0.0:
                continue
            normal = normalize_vector(normal)

            D = -v1.x*normal.x + -v1.y*normal.y + -v1.z*normal.z

            if normal.y*dir_y == 0.0:#abs(normal[1] * dir_y) < 10**(-6):
                continue # triangle parallel to ray

            t = -(normal.x * x + normal.y * y + normal.z * z + D) / (normal.y*dir_y)

            point = Vector3(x, (y+dir_y*t), z)
            #print(point)
            edg1 = create_vector(v1, v2)
            edg2 = create_vector(v2, v3)
            edg3 = create_vector(v3, v1)

            vectest1 = cross_product(edg1, create_vector(v1, point))
            vectest2 = cross_product(edg2, create_vector(v2, point))
            vectest3 = cross_product(edg3, create_vector(v3, point))

            if ((normal.dot(vectest1)) >= 0 and (normal.dot(vectest2)) >= 0 and (normal.dot(vectest3)) >= 0):

                height = point.y
                if hit is None or abs(y - height) < abs(y - hit):
                    hit = height

        return hit

    def collide_ray(self, ray):
        best_distance = None
        place_at = None

        for tri in self.triangles:
            collision = ray.collide(tri)

            if collision is not False:
                point, distance = collision

                if best_distance is None or distance < best_distance:
                    place_at = point
                    best_distance = distance

        return place_at