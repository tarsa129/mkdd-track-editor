# Python 3 necessary
from struct import unpack
from .vectors import Vector3

def read_int16(f):
    return unpack(">h", f.read(2))[0]

def read_uint16(f):
    return unpack(">H", f.read(2))[0]

def read_uint32(f):
    return unpack(">I", f.read(4))[0]

def read_float(f):
    return unpack(">f", f.read(4))[0]

def read_uint32_triple(f):
    return unpack(">III", f.read(12))

class RacetrackCollision(object):
    def __init__(self):
        self._data = None

        self.entrycount = 0

        self.grids = []
        self.triangles = []
        self.vertices = []

    def load_file(self, f):

        data = f.read()
        f.seek(0)
        self._data = data
       
        vertices_offset = read_uint32(f)
        normals_offset = read_uint32(f)
        triangles_offset = read_uint32(f) + 0x10
        spatial_offset = read_uint32(f)


        # parse vertices
        f.seek(vertices_offset)
        vertices = []
        vertices_count = (normals_offset - vertices_offset) // 0xC
        for i in range(vertices_count):
            vertices.append( Vector3(*unpack(">fff", f.read(12))) )

        # parse normals
        f.seek(normals_offset)
        normals = []
        normals_count = (triangles_offset - normals_offset) // 0xC
        for i in range(normals_count):
            normals.append( Vector3(*unpack(">fff", f.read(12))) )
        
        # Parse triangles
        f.seek(triangles_offset)
        trianglescount = (spatial_offset - triangles_offset) // 0x10
        

        for i in range(trianglescount):
            length = read_float(f)
            v1_index = read_uint16(f)
            dir_index = read_uint16(f)
            norma_index = read_uint16(f)
            normb_index = read_uint16(f)
            normc_index = read_uint16(f)

            collision_type = read_uint16(f)

            assert(v1_index < vertices_count)
            assert(dir_index < normals_count)
            assert(norma_index < normals_count)
            assert(normb_index < normals_count)
            assert(normc_index < normals_count)

            v1 = vertices[v1_index]
            direc = normals[dir_index]
            norma = normals[norma_index]
            normb = normals[normb_index]
            normc = normals[normc_index]

            crossa = norma.cross(direc)
            crossb = normb.cross(direc)

            if crossb.dot(normc) != 0 and crossa.dot(normc) != 0:
                v2 = v1 + crossb * (length / crossb.dot(normc))
                #check for float division by zero
                v3 = v1 + crossa * (length / crossa.dot(normc))

                self.triangles.append((v1,v2,v3, collision_type))

