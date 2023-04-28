import os
import json

from collections import OrderedDict
from PyQt5.QtWidgets import QSizePolicy, QWidget, QVBoxLayout, QPushButton, QGridLayout
from lib.vectors import Vector3
from PyQt5.QtCore import pyqtSignal
from lib.libkmp import *
from widgets.tree_view import KMPHeader, EnemyRoutePoint
#will create buttons based on the current selection
#when something selected: add to it from the end

class MoreButtons(QWidget):
    def __init__(self, parent, option = 0):
        super().__init__(parent)
        #self.parent = parent
        self.vbox = QVBoxLayout(self)
        self.vbox.setContentsMargins(0, 0, 0, 0)

    def add_button(self, text, option, obj):
        new_enemy_group = QPushButton(self)
        new_enemy_group.setText(text)
        new_enemy_group.clicked.connect(
            lambda: self.parent().parent.button_side_button_action(option, obj) )
        self.vbox.addWidget(new_enemy_group)

    #where the list of buttons is defined
    def add_buttons(self, obj = None):
        self.clear_buttons()

        if obj is None or isinstance(obj, KMPHeader):
            return

        if isinstance(obj, (KMPPoint, PointGroup, PointGroups)):
            point_type = "Enemy"
            if isinstance(obj, (ItemPoint, ItemPointGroup, ItemPointGroups) ):
                point_type = "Item"
            if isinstance(obj, (Checkpoint, CheckpointGroup, CheckpointGroups) ):
                point_type = "Checkpoint"

            if isinstance(obj, PointGroups):
                self.add_button("v: Add New" + point_type + " Points", "add_enemygroup", obj)

            elif isinstance(obj, KMPPoint):
                self.add_button("v: Add " + point_type + " Points Here", "new_enemy_points", obj)

        if isinstance(obj, (EnemyPointGroups, ItemPointGroups)):
            action_text = "Copy To Item Paths" if isinstance(obj, EnemyPointGroups) else "Copy From Enemy Paths"
            self.add_button(action_text, "copy_enemy_item", obj)

        elif isinstance(obj, CheckpointGroups):
            self.add_button("Auto Key Checkpoints", "auto_keycheckpoints", obj)
            self.add_button("Assign to Closest Respawn", "assign_jgpt_ckpt", obj)

        elif isinstance(obj, Checkpoint):
            self.add_button("Assign to Closest Respawn", "assign_jgpt_ckpt", obj)

        elif isinstance(obj, RoutePoint):
            self.add_button("v: Add Route Points Here", "add_routepoints", obj)

        elif isinstance(obj, MapObjects):
            self.add_button("Auto Route All Objects", "auto_route", obj)
            self.add_button("Add Generic Object", "add_object", 0)
            self.add_button("Add Item Box", "add_object", 101)
            self.add_button("Add group_enemy_c", "add_object", 702)
            self.objgrid = QGridLayout()

            self.vbox.addLayout(self.objgrid)

        elif isinstance(obj, MapObject):

            route_stuff = obj.route_info

            if route_stuff:
                self.add_button("v: Add Points to End of Route", "add_routepoints_end", obj)
                self.add_button("Auto Route", "auto_route_single", obj)
                self.add_button("Copy and Place Current Object (Same Route)", "generic_copy", obj.copy())
                self.add_button("Copy and Place Current Object (New Route)", "generic_copy_routed", obj.copy())
            else:
                self.add_button("Copy and Place Current Object", "generic_copy", obj.copy())

        elif isinstance(obj, ReplayAreas):
            self.add_button("Add Area/Stationary Cam", "add_rarea_stat", obj)
            self.add_button("Add Area/Stationary Cam", "add_rarea_rout", obj)

        elif isinstance(obj, Areas):
            self.add_button("Add Environment Effect Area", "add_area_gener", 1)
            self.add_button("Add BFG Swapper Area", "add_area_gener", 2)
            self.add_button("Add Moving Road Area With Route", "add_area_gener", 3)
            self.add_button("Add Destination Point Area", "add_area_gener", 4)
            self.add_button("Add Minimap Control Area", "add_area_gener", 5)
            self.add_button("Add BBLM Swapper", "add_area_gener", 6)
            self.add_button("Add Flying Boos Area", "add_area_gener", 7)
            self.add_button("Add Object Grouper/Unloading Areas", "add_area_objs", obj)
            self.add_button("Add Fall Boundary Area", "add_area_gener", 10)

        elif isinstance(obj, Area):
            area : Area = obj
            if area.type == 0:
                self.add_button("Copy With Same Camera", "copy_area_camera", obj)
            elif area.type == 3:
                self.add_button("Copy With Same Camera", "auto_route_single", obj)
            elif area.type == 4:
                self.add_button("Assign to Closest Enemypoint", "auto_route_single", obj)

        elif isinstance(obj, OpeningCamera):

            if obj.has_route():
                self.add_button("Copy and Place Camera (New Route)", "generic_copy_routed", obj.copy())
            else:
                self.add_button("Copy and Place Camera", "generic_copy", obj.copy())

        elif isinstance(obj, Cameras):
            self.add_button("Remove Unused Cameras", "remove_unused_cams", obj)
            self.add_button("Add Opening Camera Type 4 (KartPathFollow)", "add_camera", 4)
            self.add_button("Add Opening Camera Type 5 with Route (OP_FixMoveAt)", "add_camera", 5)

            if not obj.get_type(0):
                self.add_button("Add Goal Camera", "add_camera", 0)

        elif isinstance(obj, ObjectContainer) and obj.assoc is JugemPoint:
            self.add_button("v: Add Respawn and Assign to Closest Checkpoints", "add_jgpt", True)
            self.add_button("Auto Respawns (Create from Checkpoints)", "autocreate_jgpt", obj)
            self.add_button("Add Respawn", "add_jgpt", False)
            self.add_button("Auto Respawns (Assign All Where Closest)", "assign_jgpt_ckpt", obj)
            self.add_button("Remove Unused Respawn Points", "removed_unused_jgpt", obj)

        elif isinstance(obj, JugemPoint):
            self.add_button("Assign to Checkpoints Where Closest", "assign_jgpt_ckpt", obj)

    def add_buttons_multi(self, objs):
        self.clear_buttons()
        options= self.check_options(objs)
        #item box fill in - two item box

        #align to x and z should always be options
        self.add_button("Align on X Axis", "align_x", objs)
        self.add_button("Align on Z Axis", "align_z", objs)

        if 0 in options:
            self.add_button("Add Item Boxes Between", "aliadd_items_between", options[0])
            self.add_button("Add Item Boxes Between", "add_items_between_ground", options[0])

        if 3 in options:
            self.add_button("Decrease Scale by 5", "dec_enemy_scale", options[3])
            self.add_button("Increase Scale by 5", "inc_enemy_scale", options[3])

    def check_options(self, objs):
        #item box check for fill in
        options = {}
        item_boxes = self.check_objects(objs, (MapObject), "objectid", 101)
        if len(item_boxes) == 2:
            options[0] = item_boxes

        checkpoints = self.check_objects(objs, (Checkpoint))
        if len(checkpoints) > 0 :
            options[2] = checkpoints

        enemy_points = self.check_objects(objs, (EnemyPoint))
        if len(enemy_points) > 0:
            options[3] = enemy_points

        item_points = self.check_objects(objs, (ItemPoint))
        if len(item_points) > 0:
            options[4] = item_points


        return options

    def check_objects(self, objs, obj_types, option_name = None, option = None):
        valid_objs = []
        for obj in objs:
            valid_type = isinstance(obj, obj_types)
            if valid_type:
                if option_name is not None and hasattr(obj, option_name) and getattr(obj, option_name) == option:
                    valid_objs.append(obj)
                elif option_name is None:
                    valid_objs.append(obj)
        return valid_objs

    def clear_buttons(self):
        for i in reversed(range(self.vbox.count())):
            self.vbox.itemAt(i).widget().setParent(None)