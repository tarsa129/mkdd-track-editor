import os
import json

from collections import OrderedDict
from PyQt5.QtWidgets import QSizePolicy, QWidget, QVBoxLayout, QPushButton
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

        if obj is None or isinstance(option, KMPHeader):
            return

        if isinstance(obj, (KMPPoint, PointGroup, PointGroups)):
            point_type = "Enemy"
            if isinstance(obj, (ItemPoint, ItemPointGroup, ItemPointGroups) ):
                point_type = "Item"
            if isinstance(obj, (Checkpoint, CheckpointGroup, CheckpointGroups) ):
                point_type = "Checkpoint"

            if isinstance(obj, PointGroups):
                self.add_button("v: Add New" + point_type + " Points", "add_enemygroup", obj)

                merge_paths = QPushButton(self)
                merge_paths.setText("Merge " + point_type + " Paths")
                merge_paths.clicked.connect(lambda: self.parent.button_add_from_addi_options(10, obj) )
                self.vbox.addWidget(merge_paths)

                remove_empty = QPushButton(self)
                remove_empty.setText("Remove Disconnected " + point_type + " Paths")
                remove_empty.clicked.connect(lambda: self.parent.button_add_from_addi_options(23, obj) )
                self.vbox.addWidget(remove_empty)

            elif isinstance(obj, KMPPoint):
                new_enemy_point = QPushButton(self)
                new_enemy_point.setText("v: Add " + point_type + " Points Here")
                new_enemy_point.clicked.connect(lambda: self.parent.button_add_from_addi_options(11, obj) )
                self.vbox.addWidget(new_enemy_point)

        if isinstance(obj, (EnemyPointGroups, ItemPointGroups)):
                action_text = "Copy To Item Paths" if isinstance(obj, EnemyPointGroups) else "Copy From Enemy Paths"
                copy_from_item = QPushButton(self)
                copy_from_item.setText(action_text)
                copy_from_item.clicked.connect(lambda: self.parent.button_add_from_addi_options(24) )
                self.vbox.addWidget(copy_from_item)


        if isinstance(obj, EnemyPointGroups):
            self.add_button("Add Enemy Path", "add_enemypath", obj)
        elif isinstance(obj, (EnemyPointGroup, EnemyPoint)):
            self.add_button("Add Enemy Points", "add_enemypoints", obj)

        elif isinstance(obj, CheckpointGroups):
            set_key_automatically = QPushButton(self)
            set_key_automatically.setText("Auto Key Checkpoints")
            set_key_automatically.clicked.connect(lambda: self.parent.button_add_from_addi_options(21, obj) )
            self.vbox.addWidget(set_key_automatically)

            set_to_closest = QPushButton(self)
            set_to_closest.setText("Assign to Closest Respawn")
            set_to_closest.clicked.connect(lambda: self.parent.button_add_from_addi_options(2, obj) )
            self.vbox.addWidget(set_to_closest)

        elif isinstance(obj, Checkpoint):

            set_to_closest = QPushButton(self)
            set_to_closest.setText("Assign to Closest Respawn")
            set_to_closest.clicked.connect(lambda: self.parent.button_add_from_addi_options(2, obj) )
            self.vbox.addWidget(set_to_closest)

        elif isinstance(obj, RoutePoint):

            new_point_here = QPushButton(self)
            new_point_here.setText("v: Add Route Points Here")
            new_point_here.clicked.connect(lambda: self.parent.button_add_from_addi_options(15, obj) )
            self.vbox.addWidget(new_point_here)

        elif isinstance(obj, MapObjects):
            auto_route_all = QPushButton(self)
            auto_route_all.setText("Auto Route All Objects")
            auto_route_all.clicked.connect(lambda: self.parent.button_add_from_addi_options(17, obj) )
            self.vbox.addWidget(auto_route_all)

            new_item_box = QPushButton(self)
            new_item_box.setText("Add Generic Object")
            new_item_box.clicked.connect(lambda: self.parent.button_add_from_addi_options(3, 0) )
            self.vbox.addWidget(new_item_box)

            new_item_box = QPushButton(self)
            new_item_box.setText("Add Item Box")
            new_item_box.clicked.connect(lambda: self.parent.button_add_from_addi_options(3, 101) )
            self.vbox.addWidget(new_item_box)

            new_item_box = QPushButton(self)
            new_item_box.setText("Add group_enemy_c")
            new_item_box.clicked.connect(lambda: self.parent.button_add_from_addi_options(3, 702) )
            self.vbox.addWidget(new_item_box)

            #place several item boxes in a line

        elif isinstance(obj, MapObject):

            route_stuff = obj.route_info

            if route_stuff:

                add_points_end = QPushButton(self)
                add_points_end.setText("v: Add Points to End of Route")
                add_points_end.clicked.connect(lambda: self.parent.button_add_from_addi_options(6, obj) )
                self.vbox.addWidget(add_points_end)

                do_auto_route = QPushButton(self)
                do_auto_route.setText("Auto Route")
                do_auto_route.clicked.connect(lambda: self.parent.button_add_from_addi_options(16, obj) )
                self.vbox.addWidget(do_auto_route)

                new_item_copy = QPushButton(self)
                new_item_copy.setText("Copy and Place Current Object (Same Route)")
                new_item_copy.clicked.connect(lambda: self.parent.button_add_from_addi_options(4, obj.copy()) )
                self.vbox.addWidget(new_item_copy)

                new_item_copy = QPushButton(self)
                new_item_copy.setText("Copy and Place Current Object (New Route)")
                new_item_copy.clicked.connect(lambda: self.parent.button_add_from_addi_options(4.5, obj.copy()) )
                self.vbox.addWidget(new_item_copy)

            else:

                new_item_copy = QPushButton(self)
                new_item_copy.setText("Copy and Place Current Object")
                new_item_copy.clicked.connect(lambda: self.parent.button_add_from_addi_options(4, obj.copy()) )
                self.vbox.addWidget(new_item_copy)

        elif isinstance(obj, ReplayAreas):
            new_camera_cam_route = QPushButton(self)
            new_camera_cam_route.setText("Add Area/Stationary Cam")
            new_camera_cam_route.clicked.connect(lambda: self.parent().parent.button_add_from_addi_options(12.5) )
            self.vbox.addWidget(new_camera_cam_route)

            new_camera_cam_route = QPushButton(self)
            new_camera_cam_route.setText("Add Area/Routed Cam/Route")
            new_camera_cam_route.clicked.connect(lambda: self.parent.button_add_from_addi_options(12) )
            self.vbox.addWidget(new_camera_cam_route)

        elif isinstance(obj, Areas):
            new_area = QPushButton(self)
            new_area.setText("Add Environment Effect Area")
            new_area.clicked.connect(lambda: self.parent.button_add_from_addi_options(7, 1) )
            self.vbox.addWidget(new_area)

            new_area_2 = QPushButton(self)
            new_area_2.setText("Add BFG Swapper Area")
            new_area_2.clicked.connect(lambda: self.parent.button_add_from_addi_options(7, 2) )
            self.vbox.addWidget(new_area_2)

            new_area_3 = QPushButton(self)
            new_area_3.setText("Add Moving Road Area With Route")
            new_area_3.clicked.connect(lambda: self.parent.button_add_from_addi_options(7, 3) )
            self.vbox.addWidget(new_area_3)

            new_area_4 = QPushButton(self)
            new_area_4.setText("Add Destination Point Area")
            new_area_4.clicked.connect(lambda: self.parent.button_add_from_addi_options(7, 4) )
            self.vbox.addWidget(new_area_4)

            new_area_5 = QPushButton(self)
            new_area_5.setText("Add Minimap Control Area")
            new_area_5.clicked.connect(lambda: self.parent.button_add_from_addi_options(7, 5) )
            self.vbox.addWidget(new_area_5)

            new_area_6 = QPushButton(self)
            new_area_6.setText("Add BBLM Swapper")
            new_area_6.clicked.connect(lambda: self.parent.button_add_from_addi_options(7, 6) )
            self.vbox.addWidget(new_area_6)

            new_area_7 = QPushButton(self)
            new_area_7.setText("Add Flying Boos Area")
            new_area_7.clicked.connect(lambda: self.parent.button_add_from_addi_options(7, 7) )
            self.vbox.addWidget(new_area_7)

            new_area_8 = QPushButton(self)
            new_area_8.setText("Add Object Grouper/Unloading Areas")
            new_area_8.clicked.connect(lambda: self.parent.button_add_from_addi_options(7.5) )
            self.vbox.addWidget(new_area_8)

            new_area_a = QPushButton(self)
            new_area_a.setText("Add Fall Boundary Area")
            new_area_a.clicked.connect(lambda: self.parent.button_add_from_addi_options(7, 10) )
            self.vbox.addWidget(new_area_a)

        elif isinstance(obj, Area):
            area : Area = obj
            if area.type == 0:
                copy_same_cam = QPushButton(self)
                copy_same_cam.setText("Copy With Same Camera")
                copy_same_cam.clicked.connect(lambda: self.parent.button_add_from_addi_options(13, obj) )
                self.vbox.addWidget(copy_same_cam)
            elif area.type == 3:
                create_route = QPushButton(self)
                create_route.setText("Add Object Route")
                create_route.clicked.connect(lambda: self.parent.button_add_from_addi_options(16, obj) )
                self.vbox.addWidget(create_route)
            elif area.type == 4:
                assign_to_closest = QPushButton(self)
                assign_to_closest.setText("Assign to Closest Enemypoint")
                assign_to_closest.clicked.connect(lambda: self.parent.button_add_from_addi_options(16, obj) )
                self.vbox.addWidget(assign_to_closest)
                # delete with camera / route



        elif isinstance(obj, OpeningCamera):

            if obj.has_route():
                copy_camera = QPushButton(self)
                copy_camera.setText("Copy and Place Camera (New Route)")
                copy_camera.clicked.connect(lambda: self.parent.button_add_from_addi_options(4.5, obj.copy()) )
                self.vbox.addWidget(copy_camera)
            else:
                copy_camera = QPushButton(self)
                copy_camera.setText("Copy and Place Camera")
                copy_camera.clicked.connect(lambda: self.parent.button_add_from_addi_options(4, obj.copy()) )
                self.vbox.addWidget(copy_camera)

        elif isinstance(obj, Cameras):

            remove_unused_cams = QPushButton(self)
            remove_unused_cams.setText("Remove Unused Cameras")
            remove_unused_cams.clicked.connect(lambda: self.parent.button_add_from_addi_options(25, obj) )
            self.vbox.addWidget(remove_unused_cams)

            new_camera = QPushButton(self)
            new_camera.setText("Add Opening Camera Type 4 (KartPathFollow)")
            new_camera.clicked.connect(lambda: self.parent.button_add_from_addi_options(8, 4) )
            self.vbox.addWidget(new_camera)

            new_camera = QPushButton(self)
            new_camera.setText("Add Opening Camera Type 5 with Route (OP_FixMoveAt)")
            new_camera.clicked.connect(lambda: self.parent.button_add_from_addi_options(8, 5) )
            self.vbox.addWidget(new_camera)

            if not obj.get_type(0):
                new_goal = QPushButton(self)
                new_goal.setText("Add Goal Camera")
                new_goal.clicked.connect(lambda: self.parent.button_add_from_addi_options(8, 0) )
                self.vbox.addWidget(new_goal)

        elif isinstance(obj, ObjectContainer) and obj.assoc is JugemPoint:

            new_respawn_assign = QPushButton(self)
            new_respawn_assign.setText("v: Add Respawn and Assign to Closest Checkpoints")
            new_respawn_assign.clicked.connect(lambda: self.parent.button_add_from_addi_options(9, True) )
            self.vbox.addWidget(new_respawn_assign)

            auto_respawn_existing = QPushButton(self)
            auto_respawn_existing.setText("Auto Respawns (Create from Checkpoints)")
            auto_respawn_existing.clicked.connect(lambda: self.parent.button_add_from_addi_options(22, obj) )
            self.vbox.addWidget(auto_respawn_existing)

            new_respawn = QPushButton(self)
            new_respawn.setText("Add Respawn")
            new_respawn.clicked.connect(lambda: self.parent.button_add_from_addi_options(9, False) )
            self.vbox.addWidget(new_respawn)

            auto_respawn_existing = QPushButton(self)
            auto_respawn_existing.setText("Auto Respawns (Assign All Where Closest)")
            auto_respawn_existing.clicked.connect(lambda: self.parent.button_add_from_addi_options(2, obj) )
            self.vbox.addWidget(auto_respawn_existing)

            remove_unused = QPushButton(self)
            remove_unused.setText("Remove Unused Respawn Points")
            remove_unused.clicked.connect(lambda: self.parent.button_add_from_addi_options(26, obj) )
            self.vbox.addWidget(remove_unused)
        elif isinstance(obj, JugemPoint):

            assign_only = QPushButton(self)
            assign_only.setText("Assign to Checkpoints Where Closest")
            assign_only.clicked.connect(lambda: self.parent.button_add_from_addi_options(2, obj) )
            self.vbox.addWidget(assign_only)

    def add_buttons_multi(self, objs):
        self.clear_buttons()
        options= self.check_options(objs)
        #item box fill in - two item box

        #align to x and z should always be options

        align_on_x = QPushButton(self)
        align_on_x.setText("Align on X Axis")
        align_on_x.clicked.connect(lambda: self.parent.button_add_from_addi_options_multi(-1, objs) )
        self.vbox.addWidget(align_on_x)

        align_on_z = QPushButton(self)
        align_on_z.setText("Align on Z Axis")
        align_on_z.clicked.connect(lambda: self.parent.button_add_from_addi_options_multi(-1.5, objs) )
        self.vbox.addWidget(align_on_z)

        if 0 in options:
            item_box_fill = QPushButton(self)
            item_box_fill.setText("Add Item Boxes Between")
            item_box_fill.clicked.connect(lambda: self.parent.button_add_from_addi_options_multi(0, options[0]) )
            self.vbox.addWidget(item_box_fill)

            item_box_fill = QPushButton(self)
            item_box_fill.setText("Add Item Boxes Between And Ground")
            item_box_fill.clicked.connect(lambda: self.parent.button_add_from_addi_options_multi(0.5, options[0]) )
            self.vbox.addWidget(item_box_fill)
        if 1 in options:
            assign_to_route = QPushButton(self)
            assign_to_route.setText("Assign Objects to Route")
            assign_to_route.clicked.connect(lambda: self.parent.button_add_from_addi_options_multi(1, options[1]) )
            self.vbox.addWidget(assign_to_route)
        if 3 in options:
            decrease_scale = QPushButton(self)
            decrease_scale.setText("Decrease Scale by 5")
            decrease_scale.clicked.connect(lambda: self.parent.button_add_from_addi_options_multi(2, options[3]) )
            self.vbox.addWidget(decrease_scale)

            increase_scale = QPushButton(self)
            increase_scale.setText("Increase Scale by 5")
            increase_scale.clicked.connect(lambda: self.parent.button_add_from_addi_options_multi(2.5, options[3]) )
            self.vbox.addWidget(increase_scale)

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