import os
import json
from OpenGL.GL import *
from .model_rendering import (GenericObject, Model, TexturedModel, Cube)

with open("lib/color_coding.json", "r") as f:
    colors = json.load(f)


def do_rotation(rotation):
    glMultMatrixf( rotation.get_render() )
    scale = 10.0
    glScalef(scale, scale, scale ** 2)



class ObjectModels(object):
    def __init__(self):
        self.models = {}
        self.generic = GenericObject()

        self.cube = Cube()
        self.enemypoint = Cube(colors["EnemyRoutes"])
        self.enemypointfirst = Cube(colors["FirstEnemyPoint"])
        self.itempoint = Cube(colors["ItemRoutes"])
        self.itempointfirst = Cube(colors["FirstItemPoint"])

        self.checkpointleft = Cube(colors["CheckpointLeft"])
        self.checkpointright = Cube(colors["CheckpointRight"])

        self.objects = GenericObject(colors["Objects"])
        self.objectpoint = Cube(colors["ObjectRoutes"])
        self.unusedobjectpoint = Cube(colors["UnusedObjectRoutes"])

        self.areapoint = Cube(colors["AreaRoutes"])
        self.camerapoint = Cube(colors["CameraRoutes"])
        self.unusedpoint = Cube(colors["UnusedRoutes"])
        self.camera = GenericObject(colors["Camera"])
        self.areas = GenericObject(colors["Areas"])

        self.respawn = GenericObject(colors["Respawn"])
        self.unusedrespawn = GenericObject(colors["UnusedRespawn"])

        self.startpoints = GenericObject(colors["StartPoints"])
        self.cannons = GenericObject(colors["Cannons"])
        self.missions = GenericObject(colors["Missions"])

        #self.purplecube = Cube((0.7, 0.7, 1.0, 1.0))

        self.playercolors = [Cube(color) for color in ((1.0, 0.0, 0.0, 1.0),
                                                       (0.0, 0.0, 1.0, 1.0),
                                                       (1.0, 1.0, 0.0, 1.0),
                                                       (0.0, 1.0, 1.0, 1.0),
                                                       (1.0, 0.0, 1.0, 1.0),
                                                       (1.0, 0.5, 0.0, 1.0),
                                                       (0.0, 0.5, 1.0, 1.0),
                                                       (1.0, 0.0, 0.5, 1.0))]

        with open("resources/unitsphere.obj", "r") as f:
            self.sphere = Model.from_obj(f, rotate=True)

        with open("resources/unitcylinder.obj", "r") as f:
            self.cylinder = Model.from_obj(f, rotate=True)

        with open("resources/unitcylinder.obj", "r") as f:
            self.wireframe_cylinder = Model.from_obj(f, rotate=True)

        with open("resources/unitcube_wireframe.obj", "r") as f:
            self.wireframe_cube = Model.from_obj(f, rotate=True)

        with open("resources/arrow_head.obj", "r") as f:
            self.arrow_head = Model.from_obj(f, rotate=True, scale=500.0)

    def init_gl(self):
        for dirpath, dirs, files in os.walk("resources/objectmodels"):
            for file in files:
                if file.endswith(".obj"):
                    filename = os.path.basename(file)
                    objectname = filename.rsplit(".", 1)[0]
                    self.models[objectname] = TexturedModel.from_obj_path(os.path.join(dirpath, file), rotate=True)
        for cube in (self.cube, self.checkpointleft, self.checkpointright, self.camerapoint, self.objectpoint, 
                     self.enemypoint, self.enemypointfirst, self.itempoint, self.itempointfirst,
                     self.objects, self.areas, self.respawn, self.startpoints, self.camera, self.unusedpoint, self.areapoint,
                     self.unusedobjectpoint, self.unusedrespawn,
                     self.cannons, self.missions):
            cube.generate_displists()

        for cube in self.playercolors:
            cube.generate_displists()

        self.generic.generate_displists()

    def draw_arrow_head(self, frompos, topos):
        glPushMatrix()
        dir = topos-frompos
        if not dir.is_zero():
            dir.normalize()
            glMultMatrixf([dir.x, -dir.z, 0, 0,
                           -dir.z, -dir.x, 0, 0,
                           0, 0, 1, 0,
                           topos.x, -topos.z, topos.y, 1])
        else:
            glTranslatef(topos.x, -topos.z, topos.y)
        self.arrow_head.render()
        glPopMatrix()
        #glBegin(GL_LINES)
        #glVertex3f(frompos.x, -frompos.z, frompos.y)
        #glVertex3f(topos.x, -topos.z, topos.y)
        #glEnd()

    def draw_sphere(self, position, scale):
        glPushMatrix()

        glTranslatef(position.x, -position.z, position.y)

        glScalef(scale, scale, scale)

        self.sphere.render()
        glPopMatrix()

    def draw_sphere_last_position(self, scale):
        glPushMatrix()

        glScalef(scale, scale, scale)

        self.sphere.render()
        glPopMatrix()

    def draw_cylinder(self,position, radius, height):
        glPushMatrix()

        glTranslatef(position.x, -position.z, position.y)
        glScalef(radius, height, radius)

        self.cylinder.render()
        glPopMatrix()

    def draw_wireframe_cylinder(self, position, rotation, scale):
        glPushMatrix()
        glTranslatef(position.x, -position.z, position.y)
        #mtx = rotation.mtx
        #glMultMatrixf(mtx)
        do_rotation(rotation)
        glTranslatef(0, 0, scale.y / 2)
        glScalef(scale.x, scale.z, scale.y)
        self.wireframe_cylinder.render()
        glPopMatrix()

    def draw_wireframe_cube(self, position, rotation, scale, kartstart = False):
        glPushMatrix()
        glTranslatef(position.x, -position.z, position.y)
        #glTranslatef(position.x, position.y, position.z)
        #mtx = rotation.mtx
        #glMultMatrixf(mtx)

        do_rotation(rotation)
        glTranslatef(0, 0, scale.y/2)

        if kartstart:
            glTranslatef(-scale.z / 2, 0, 0)

        glScalef(scale.z, scale.x, scale.y)
        self.wireframe_cube.render()
        glPopMatrix()

    def draw_cylinder_last_position(self, radius, height):
        glPushMatrix()

        glScalef(radius, radius, height)

        self.cylinder.render()
        glPopMatrix()

    def render_generic_position(self, position, selected):
        self._render_generic_position(self.cube, position, selected)

    def render_generic_position_colored(self, position, selected, cubename):
        self._render_generic_position(getattr(self, cubename), position, selected)

    def render_player_position_colored(self, position, selected, player):
        self._render_generic_position(self.playercolors[player], position, selected)

    def render_generic_position_rotation(self, position, rotation, selected):
        self._render_generic_position_rotation("generic", position, rotation, selected)

    def render_generic_position_rotation_colored(self, objecttype, position, rotation, selected):
        self._render_generic_position_rotation(objecttype, position, rotation, selected)

    def _render_generic_position_rotation(self, name, position, rotation, selected):
        glPushMatrix()
        glTranslatef(position.x, -position.z, position.y)
        #glTranslatef(position.x, position.y, position.z)


        do_rotation(rotation)

        glColor3f(0.0, 0.0, 0.0)
        glBegin(GL_LINE_STRIP)
        glVertex3f(0.0, 0.0, 750.0)
        glVertex3f(0.0, 0.0, 0.0)
        glVertex3f(1000.0, 0.0, 0.0)
        glEnd()

        #glScalef(1.0, 1.0, 1.0)
        getattr(self, name).render(selected=selected)

        glPopMatrix()

    def _render_generic_position(self, cube, position, selected):
        glPushMatrix()
        glTranslatef(position.x, -position.z, position.y)
        #glTranslatef(position.x, position.y, position.z)
        cube.render(selected=selected)

        glPopMatrix()

    def render_generic_position_colored_id(self, position, id):
        glPushMatrix()
        glTranslatef(position.x, -position.z, position.y)
        glScale(2.0, 2.0, 2.0)
        #glTranslatef(position.x, position.y, position.z)
        self.cube.render_coloredid(id)

        glPopMatrix()

    def render_generic_position_rotation_colored_id(self, position, rotation, id):
        glPushMatrix()
        glTranslatef(position.x, -position.z, position.y)
        #glTranslatef(position.x, position.y, position.z)


        #mtx = rotation.mtx
        #glMultMatrixf(mtx)

        do_rotation(rotation)
        glScale(2.0, 2.0, 2.0)
        self.cube.render_coloredid(id)

        glPopMatrix()

    def render_line(self, pos1, pos2):
        pass


