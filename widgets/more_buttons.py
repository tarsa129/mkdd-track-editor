import os
import json

from collections import OrderedDict
from PyQt5.QtWidgets import QSizePolicy, QWidget, QVBoxLayout, QPushButton
from lib.vectors import Vector3
from PyQt5.QtCore import pyqtSignal
from lib.libkmp import (EnemyPoint, EnemyPointGroup, EnemyPointGroups, ItemPoint, ItemPointGroup, ItemPointGroups, CheckpointGroups, CheckpointGroup, Checkpoint, Route, RoutePoint, Area, Areas,
                        MapObject, KartStartPoint, Camera, KMP, JugemPoint, MapObjects, MapObject,
                         OBJECTNAMES, ObjectContainer, KartStartPoints, PointGroups, PointGroup, KMPPoint)
from widgets.tree_view import KMPHeader, EnemyRoutePoint
#will create buttons based on the current selection
#when nothing selected - add anything
#when something selected: add to it from the end




class MoreButtons(QWidget):
    def __init__(self, parent, option = 0):
        super().__init__(parent)
        self.parent = parent
        self.vbox = QVBoxLayout(self)
        
    #where the list of buttons is defined
    def add_buttons(self, option = None):
        self.clear_buttons()
        all_options = False

        
        if option is None or isinstance(option, KMPHeader): #nothing selected and top level stuff
            return

        obj = option.bound_to
        if isinstance(obj, (KMPPoint, PointGroup, PointGroups)):
            point_type = "Enemy"
            if isinstance(obj, (ItemPoint, ItemPointGroup, ItemPointGroups) ):
                point_type = "Item"
            if isinstance(obj, (Checkpoint, CheckpointGroup, CheckpointGroups) ):
                point_type = "Checkpoint"
        
            if isinstance(obj, PointGroups):
                new_enemy_group = QPushButton(self)
                new_enemy_group.setText("Add " + point_type + " Path")
                new_enemy_group.clicked.connect(lambda: self.parent.button_add_from_addi_options(0, option.bound_to) )
                self.vbox.addWidget(new_enemy_group)

                merge_paths = QPushButton(self)
                merge_paths.setText("Merge " + point_type + " Paths")
                merge_paths.clicked.connect(lambda: self.parent.button_add_from_addi_options(10, option.bound_to) )
                self.vbox.addWidget(merge_paths)


            elif isinstance(obj, PointGroup):
                new_enemy_group = QPushButton(self)
                new_enemy_group.setText("Add " + point_type + " Path")
                new_enemy_group.clicked.connect(lambda: self.parent.button_add_from_addi_options(0, option.bound_to) )
                self.vbox.addWidget(new_enemy_group)

                new_enemy_point = QPushButton(self)
                new_enemy_point.setText("Add " + point_type + " Points To End Of Path")
                new_enemy_point.clicked.connect(lambda: self.parent.button_add_from_addi_options(1, option.bound_to) )
                self.vbox.addWidget(new_enemy_point)
            elif isinstance(obj, KMPPoint):
                all_options = False
                new_enemy_point = QPushButton(self)
                new_enemy_point.setText("Add " + point_type + " Points Here")
                new_enemy_point.clicked.connect(lambda: self.parent.button_add_from_addi_options(11, option.bound_to) )
                self.vbox.addWidget(new_enemy_point)
        
        if isinstance(obj, (EnemyPointGroups, ItemPointGroups)):
                action_text = "Copy To Item Paths" if isinstance(option.bound_to, EnemyPointGroups) else "Copy From Enemy Paths"
                copy_from_item = QPushButton(self)
                copy_from_item.setText(action_text)
                copy_from_item.clicked.connect(lambda: self.parent.button_add_from_addi_options(24) )
                self.vbox.addWidget(copy_from_item)

        elif isinstance(option.bound_to, CheckpointGroups):
            all_options = False

            set_key_automatically = QPushButton(self)
            set_key_automatically.setText("Auto Key Checkpoints")
            set_key_automatically.clicked.connect(lambda: self.parent.button_add_from_addi_options(21, option.bound_to) )
            self.vbox.addWidget(set_key_automatically)

            set_to_closest = QPushButton(self)
            set_to_closest.setText("Assign to Closest Respawn")
            set_to_closest.clicked.connect(lambda: self.parent.button_add_from_addi_options(2, obj) )
            self.vbox.addWidget(set_to_closest)
            
        elif isinstance(option.bound_to, Checkpoint):
            
            all_options = False
            set_to_closest = QPushButton(self)
            set_to_closest.setText("Assign to Closest Respawn")
            set_to_closest.clicked.connect(lambda: self.parent.button_add_from_addi_options(2, obj) )
            self.vbox.addWidget(set_to_closest)
            
        elif isinstance(option.bound_to, Route):     
            new_route_point = QPushButton(self)
            new_route_point.setText("Add Route Points To End")  
            new_route_point.clicked.connect(lambda: self.parent.button_add_from_addi_options(6, option.bound_to) )  
            self.vbox.addWidget(new_route_point)
        elif isinstance(option.bound_to, RoutePoint):
            all_options = False
            new_point_here = QPushButton(self)
            new_point_here.setText("Add Route Points Here")
            new_point_here.clicked.connect(lambda: self.parent.button_add_from_addi_options(15, option.bound_to) )
            self.vbox.addWidget(new_point_here)
        
        elif isinstance(option.bound_to, MapObjects):
            all_options = False
            
            auto_route_all = QPushButton(self)
            auto_route_all.setText("Auto Route All Objects")
            auto_route_all.clicked.connect(lambda: self.parent.button_add_from_addi_options(17, option.bound_to) )
            self.vbox.addWidget(auto_route_all)
            
            new_item_box = QPushButton(self)
            new_item_box.setText("Add Item Box")
            new_item_box.clicked.connect(lambda: self.parent.button_add_from_addi_options(3, 101) )
            self.vbox.addWidget(new_item_box)

            new_item_box = QPushButton(self)
            new_item_box.setText("Add group_enemy_c")
            new_item_box.clicked.connect(lambda: self.parent.button_add_from_addi_options(3, 702) )
            self.vbox.addWidget(new_item_box)
            
            #place several item boxes in a line
            pass
        elif isinstance(option.bound_to, MapObject):   
        
            route_stuff = option.bound_to.route_info
        
            if route_stuff:
            
                do_auto_route = QPushButton(self)
                do_auto_route.setText("Auto Route")
                do_auto_route.clicked.connect(lambda: self.parent.button_add_from_addi_options(16, option.bound_to) )
                self.vbox.addWidget(do_auto_route)
            
                all_options = False
                new_item_copy = QPushButton(self)
                new_item_copy.setText("Copy and Place Current Object (Same Route)")
                new_item_copy.clicked.connect(lambda: self.parent.button_add_from_addi_options(4, option.bound_to.copy()) )
                self.vbox.addWidget(new_item_copy)
            
            
                all_options = False
                new_item_copy = QPushButton(self)
                new_item_copy.setText("Copy and Place Current Object (New Route)")
                new_item_copy.clicked.connect(lambda: self.parent.button_add_from_addi_options(4.5, option.bound_to.copy()) )
                self.vbox.addWidget(new_item_copy)
        
            else:
                all_options = False
                new_item_copy = QPushButton(self)
                new_item_copy.setText("Copy and Place Current Object")
                new_item_copy.clicked.connect(lambda: self.parent.button_add_from_addi_options(4, option.bound_to.copy()) )
                self.vbox.addWidget(new_item_copy)
      
        elif isinstance(option.bound_to, Area) or (isinstance(option.bound_to, Areas) ):
            all_options = False

            new_camera_cam_route = QPushButton(self)
            new_camera_cam_route.setText("Add Area/Stationary Cam")
            new_camera_cam_route.clicked.connect(lambda: self.parent.button_add_from_addi_options(12.5) )
            self.vbox.addWidget(new_camera_cam_route)

            new_camera_cam_route = QPushButton(self)
            new_camera_cam_route.setText("Add Area/Routed Cam/Route")
            new_camera_cam_route.clicked.connect(lambda: self.parent.button_add_from_addi_options(12) )
            self.vbox.addWidget(new_camera_cam_route)

            new_area = QPushButton(self)
            new_area.setText("Add Environment Effect Area (Type 1)")
            new_area.clicked.connect(lambda: self.parent.button_add_from_addi_options(7, 1) )
            self.vbox.addWidget(new_area)

            new_area_2 = QPushButton(self)
            new_area_2.setText("Add BFG Swapper Area (Type 2)")
            new_area_2.clicked.connect(lambda: self.parent.button_add_from_addi_options(7, 2) )
            self.vbox.addWidget(new_area_2)

            new_area_3 = QPushButton(self)
            new_area_3.setText("Add Moving Road Area (Type 3)")
            new_area_3.clicked.connect(lambda: self.parent.button_add_from_addi_options(7, 3) )
            self.vbox.addWidget(new_area_3)

            new_area_4 = QPushButton(self)
            new_area_4.setText("Add Destination Point Area (Type 4)")
            new_area_4.clicked.connect(lambda: self.parent.button_add_from_addi_options(7, 4) )
            self.vbox.addWidget(new_area_4)

            new_area_5 = QPushButton(self)
            new_area_5.setText("Add Minimap Control Area (Type 5)")
            new_area_5.clicked.connect(lambda: self.parent.button_add_from_addi_options(7, 5) )
            self.vbox.addWidget(new_area_5)

            new_area_6 = QPushButton(self)
            new_area_6.setText("Add BBLM Swapper (Type 6)")
            new_area_6.clicked.connect(lambda: self.parent.button_add_from_addi_options(7, 6) )
            self.vbox.addWidget(new_area_6)

            new_area_7 = QPushButton(self)
            new_area_7.setText("Add Flying Boos Area (Type 7)")
            new_area_7.clicked.connect(lambda: self.parent.button_add_from_addi_options(7, 7) )
            self.vbox.addWidget(new_area_7)

            new_area_8 = QPushButton(self)
            new_area_8.setText("Add Object Grouper/Unloading Areas (Types 8/9)")
            new_area_8.clicked.connect(lambda: self.parent.button_add_from_addi_options(7.5) )
            self.vbox.addWidget(new_area_8)

            new_area_a = QPushButton(self)
            new_area_a.setText("Add Fall Boundary Area (Type 10)")
            new_area_a.clicked.connect(lambda: self.parent.button_add_from_addi_options(7, 10) )
            self.vbox.addWidget(new_area_a)


        elif isinstance(option.bound_to, Camera):
        
            all_options = False
            
            
            if option.bound_to.has_route():
            #auto route camera
                do_auto_route = QPushButton(self)
                do_auto_route.setText("Auto Route")
                do_auto_route.clicked.connect(lambda: self.parent.button_add_from_addi_options(16, option.bound_to) )
                self.vbox.addWidget(do_auto_route)
                

                copy_camera = QPushButton(self)
                copy_camera.setText("Copy and Place Camera (New Route)")
                copy_camera.clicked.connect(lambda: self.parent.button_add_from_addi_options(4.5, option.bound_to.copy()) )
                self.vbox.addWidget(copy_camera)
                
                snap_camera = QPushButton(self)
                snap_camera.setText("Snap to Route")
                snap_camera.clicked.connect(lambda: self.parent.button_add_from_addi_options(19, option.bound_to) )
                self.vbox.addWidget(snap_camera)
            else:
                copy_camera = QPushButton(self)
                copy_camera.setText("Copy and Place Camera")
                copy_camera.clicked.connect(lambda: self.parent.button_add_from_addi_options(4, option.bound_to.copy()) )
                self.vbox.addWidget(copy_camera)

            
        elif isinstance(option.bound_to, ObjectContainer) and option.bound_to.assoc is Camera:
        
            all_options = False
            
            #auto route all
            auto_route_all = QPushButton(self)
            auto_route_all.setText("Auto Route All Cameras")
            auto_route_all.clicked.connect(lambda: self.parent.button_add_from_addi_options(17, option.bound_to) )
            self.vbox.addWidget(auto_route_all)
            
            remove_unused_cams = QPushButton(self)
            remove_unused_cams.setText("Remove Unused Cameras")
            remove_unused_cams.clicked.connect(lambda: self.parent.button_add_from_addi_options(25, option.bound_to) )
            self.vbox.addWidget(remove_unused_cams)
             
            snap_camera = QPushButton(self)
            snap_camera.setText("Snap All to Route")
            snap_camera.clicked.connect(lambda: self.parent.button_add_from_addi_options(20, option.bound_to) )
            self.vbox.addWidget(snap_camera)
            
            new_camera = QPushButton(self)
            new_camera.setText("Add Camera Type 4 with Route (StartFixPath)")
            new_camera.clicked.connect(lambda: self.parent.button_add_from_addi_options(8, 4) )
            self.vbox.addWidget(new_camera)

            new_camera = QPushButton(self)
            new_camera.setText("Add Camera Type 5 with Route (StartPath)")
            new_camera.clicked.connect(lambda: self.parent.button_add_from_addi_options(8, 5) )
            self.vbox.addWidget(new_camera)

            new_camera = QPushButton(self)
            new_camera.setText("Add Camera Type 6 (StartLookPath)")
            new_camera.clicked.connect(lambda: self.parent.button_add_from_addi_options(8, 6) )
            self.vbox.addWidget(new_camera)

            #add area / camera / route?
            
        elif isinstance(option.bound_to, ObjectContainer) and option.bound_to.assoc is Route:
            new_route_group = QPushButton(self)
            new_route_group.setText("Add Object Route")
            new_route_group.clicked.connect(lambda: self.parent.button_add_from_addi_options(5) )
            self.vbox.addWidget(new_route_group)

            new_cameraroute_group = QPushButton(self)
            new_cameraroute_group.setText("Add Camera Route")
            new_cameraroute_group.clicked.connect(lambda: self.parent.button_add_from_addi_options(5.5) )
            self.vbox.addWidget(new_cameraroute_group)
            
            remove_unsed = QPushButton(self)
            remove_unsed.setText("Removed Unused Routes")
            remove_unsed.clicked.connect(lambda: self.parent.button_add_from_addi_options(23, option.bound_to) )
            self.vbox.addWidget(remove_unsed)
            
            #copy camera
        elif isinstance(option.bound_to, ObjectContainer) and option.bound_to.assoc is JugemPoint:
            all_options = False


            new_respawn = QPushButton(self)
            new_respawn.setText("Add Respawn")
            new_respawn.clicked.connect(lambda: self.parent.button_add_from_addi_options(9, False) )
            self.vbox.addWidget(new_respawn)

            new_respawn_assign = QPushButton(self)
            new_respawn_assign.setText("Add Respawn and Assign to Closest Checkpoints")
            new_respawn_assign.clicked.connect(lambda: self.parent.button_add_from_addi_options(9, True) )
            self.vbox.addWidget(new_respawn_assign)

            auto_respawn_existing = QPushButton(self)
            auto_respawn_existing.setText("Auto Respawns (Create from Checkpoints)")
            auto_respawn_existing.clicked.connect(lambda: self.parent.button_add_from_addi_options(22, option.bound_to) )
            self.vbox.addWidget(auto_respawn_existing)

            auto_respawn_existing = QPushButton(self)
            auto_respawn_existing.setText("Auto Respawns (Assign All Where Closest)")
            auto_respawn_existing.clicked.connect(lambda: self.parent.button_add_from_addi_options(2, option.bound_to) )
            self.vbox.addWidget(auto_respawn_existing)

            remove_unused = QPushButton(self)
            remove_unused.setText("Remove Unused Respawn Points")
            remove_unused.clicked.connect(lambda: self.parent.button_add_from_addi_options(26, option.bound_to) )
            self.vbox.addWidget(remove_unused)
        elif isinstance(option.bound_to, JugemPoint):
            all_options = False

            assign_only = QPushButton(self)
            assign_only.setText("Assign to Checkpoints Where Closest")
            assign_only.clicked.connect(lambda: self.parent.button_add_from_addi_options(2, obj) )
            self.vbox.addWidget(assign_only)

        if all_options:
            self.add_top_level_items()
    def add_top_level_items(self):
        new_enemy_group = QPushButton(self)
        new_enemy_group.setText("Add Enemy Group")
        new_enemy_group.clicked.connect(lambda: self.parent.button_add_from_addi_options(0) )
        self.vbox.addWidget(new_enemy_group)
        
        new_check_group = QPushButton(self)
        new_check_group.setText("Add Checkpoint Group")
        new_check_group.clicked.connect(lambda: self.parent.button_add_from_addi_options(2) )
        self.vbox.addWidget(new_check_group)
        
        new_route_group = QPushButton(self)
        new_route_group.setText("Add Object Route")
        new_route_group.clicked.connect(lambda: self.parent.button_add_from_addi_options(5) )
        self.vbox.addWidget(new_route_group)

        new_cameraroute_group = QPushButton(self)
        new_cameraroute_group.setText("Add Camera Route")
        new_cameraroute_group.clicked.connect(lambda: self.parent.button_add_from_addi_options(5.5) )
        self.vbox.addWidget(new_cameraroute_group)
        
        new_respawn = QPushButton(self)
        new_respawn.setText("Add Respawn")
        new_respawn.clicked.connect(lambda: self.parent.button_add_from_addi_options(9) )
        self.vbox.addWidget(new_respawn)
        
        new_camera_cam_route = QPushButton(self)
        new_camera_cam_route.setText("Add Area/Cam/Route")
        new_camera_cam_route.clicked.connect(lambda: self.parent.button_add_from_addi_options(12) )
        self.vbox.addWidget(new_camera_cam_route)
            
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
        #routepoints - links
        
        pass
        
    def check_options(self, objs):
        #item box check for fill in
        options = {}
        item_boxes = self.check_objects(objs, [MapObject], 101)
        if len(item_boxes) == 2:
            options[0] = item_boxes
        #routed_objects = self.check_objects(objs, [MapObject, Camera])
        #if len(self.check_objects(objs, [Route])) == 1 and len(routed_objects) > 0: 
        #    options[1] = routed_objects
        checkpoints = self.check_objects(objs, [Checkpoint])
        if len(checkpoints) > 0 :
            options[2] = checkpoints
        enemy_routes = self.check_objects(objs, [EnemyPoint])
        #print("any enemy points in selection?", len(enemy_routes))
        if len(enemy_routes) > 0:
            ending_points = []
            #print('looking for enemy points')
            for point_group in self.parent.level_file.enemypointgroups.groups:
                if len(point_group.points) > 0 and point_group.points[0] in enemy_routes:
                    ending_points.append(point_group.points[0])
                
                if len(point_group.points) > 1 and point_group.points[-1] in enemy_routes:
                    ending_points.append(point_group.points[-1])
            if len(enemy_routes) > 1:
                options[3] = ending_points


        return options
        
    def check_objects(self, objs, obj_types, option = None):
        valid_objs = []
        for obj in objs:
            valid_type = self.check_obj_types(obj, obj_types)
            if valid_type is not None:
                if option is not None:
                    if valid_type == MapObject:
                        if obj.objectid == option:
                            valid_objs.append(obj)
                else:
                    valid_objs.append(obj)
        return valid_objs
    
    def check_obj_types(self, obj, obj_types):
        for obj_type in obj_types:
            if isinstance(obj, obj_type):   
                return obj_type
        return None
    
    def clear_buttons(self):
        for i in reversed(range(self.vbox.count())): 
            self.vbox.itemAt(i).widget().setParent(None)
    