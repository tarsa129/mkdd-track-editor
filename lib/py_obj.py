from struct import unpack
from OpenGL.GL import *


def read_vertex(v_data):
    split = v_data.split("/")
    if len(split) == 3:
        vnormal = int(split[2])
    else:
        vnormal = None
    v = int(split[0])
    return v, vnormal


class Mesh(object):
    def __init__(self, name):
        self.name = name
        self.primtype = "Triangles"
        self.vertices = []
        self.texcoords = []
        self.triangles = []

        self._displist = None

        self.texture = None

    def generate_displist(self):
        if self._displist is not None:
            glDeleteLists(self._displist, 1);

        displist = glGenLists(1)
        glNewList(displist, GL_COMPILE)

        for v1, v2, v3 in self.triangles:
            v1i, v1coord = v1
            v2i, v2coord = v2
            v3i, v3coord = v3
            glVertex3f(self.vertices[v1i])
            glVertex3f(self.vertices[v2i])
            glVertex3f(self.vertices[v3i])

        glEndList()

    def render(self):
        if self._displist is None:
            self.generate_displist()
        glCallList(self._displist)


class Model(object):
    def __init__(self):
        self.meshes = []

    def render(self):
        for mesh in self.meshes:
            mesh.render()

    @classmethod
    def from_obj(cls, f):
        model = cls()
        vertices = []
        texcoords = []

        curr_mesh = None

        for line in f:
            line = line.strip()
            args = line.split(" ")

            if len(args) == 0 or line.startswith("#"):
                continue
            cmd = args[0]

            if cmd == "o":
                objectname = args[1]
                if curr_mesh is not None:
                    model.meshes.append(curr_mesh)
                curr_mesh = Mesh()
                curr_mesh.vertices = vertices

            elif cmd == "v":
                if "" in args:
                    args.remove("")
                x, y, z = map(float, args[1:4])
                vertices.append((x, y, z))

            elif cmd == "f":
                if curr_mesh is None:
                    curr_mesh = Mesh("")
                    curr_mesh.vertices = vertices

                if len(args) == 5:
                    v1, v2, v3, v4 = map(read_vertex, args[1:5])
                    curr_mesh.triangles.append(((v1[0], None), (v3[0], None), (v2[0], None)))
                    curr_mesh.triangles.append(((v3[0], None), (v1[0], None), (v4[0], None)))
                elif len(args) == 4:
                    v1, v2, v3 = map(read_vertex, args[1:4])
                    curr_mesh.triangles.append(((v1[0], None), (v2[0], None), (v3[0], None)))
                elif len(args) > 5:
                    raise RuntimeError("Mesh has faces with more than 4 polygons! Only Tris and Quads supported.")
        model.meshes.append(curr_mesh)
        #elif cmd == "vn":
        #    nx, ny, nz = map(float, args[1:4])
        #    normals.append((nx, ny, nz))


def read_obj(objfile):

    vertices = []
    faces = []
    face_normals = []
    normals = []

    for line in objfile:
        line = line.strip()
        args = line.split(" ")

        if len(args) == 0 or line.startswith("#"):
            continue
        cmd = args[0]

        if cmd == "v":
            if "" in args:
                args.remove("")
            x,y,z = map(float, args[1:4])
            vertices.append((x,y,z))
        elif cmd == "f":
            # if it uses more than 3 vertices to describe a face then we panic!
            # no triangulation yet.
            if len(args) != 4:
                raise RuntimeError("Model needs to be triangulated! Only faces with 3 vertices are supported.")
            v1, v2, v3 = map(read_vertex, args[1:4])
            faces.append((v1,v2,v3))
        elif cmd == "vn":
            nx,ny,nz = map(float, args[1:4])
            normals.append((nx,ny,nz))


    #objects.append((current_object, vertices, faces))

    return vertices, faces, normals

def read_uint32(f):
    val = f.read(0x4)
    return unpack(">I", val)[0]

def read_float_tripple(f):
    val = f.read(0xC)
    return unpack(">fff", val)

def read_uint16(f):
    return unpack(">H", f.read(2))[0]

