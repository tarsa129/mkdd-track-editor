from argparse import _MutuallyExclusiveGroup
import pickle
import traceback
import os
from timeit import default_timer
from copy import deepcopy
from io import TextIOWrapper, BytesIO, StringIO
from math import sin, cos, atan2
import json
import PyQt5.QtWidgets as QtWidgets
import PyQt5.QtCore as QtCore
from PyQt5.QtCore import Qt

from PyQt5.QtWidgets import (QWidget, QMainWindow, QFileDialog, QSplitter,
                             QSpacerItem, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QHBoxLayout,
                             QScrollArea, QGridLayout, QMenuBar, QMenu, QAction, QApplication, QStatusBar, QLineEdit)
from PyQt5.QtGui import QMouseEvent, QImage
import PyQt5.QtGui as QtGui

import opengltext
import py_obj

from widgets.editor_widgets import catch_exception
from widgets.editor_widgets import AddPikObjectWindow
from widgets.tree_view import LevelDataTreeView
import widgets.tree_view as tree_view
from configuration import read_config, make_default_config, save_cfg

import mkwii_widgets 
from widgets.side_widget import PikminSideWidget
from widgets.editor_widgets import open_error_dialog, catch_exception_with_dialog
from widgets.data_editor import load_route_info
from mkwii_widgets import KMPMapViewer, MODE_TOPDOWN
from lib.libkmp import *
import lib.libkmp as libkmp
from lib.rarc import Archive
from lib.libkcl import RacetrackCollision
from lib.model_rendering import TexturedModel, CollisionModel
from widgets.editor_widgets import ErrorAnalyzer, ErrorAnalyzerButton
from widgets.file_select import FileSelect
from PyQt5.QtWidgets import QTreeWidgetItem
from lib.vectors import Vector3

def get_treeitem(root:QTreeWidgetItem, obj):
    for i in range(root.childCount()):
        child = root.child(i)
        if child.bound_to == obj:
            return child
    return None

class UndoEntry:

    def __init__(self, bol_document: bytes, enemy_path_data: 'tuple[tuple[bool, int]]'):
        self.bol_document = bol_document
        self.enemy_path_data = enemy_path_data

        self.bol_hash = hash((bol_document, enemy_path_data))
        self.hash = hash((self.bol_hash))

    def __eq__(self, other) -> bool:
        return self.hash == other.hash

class GenEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.level_file = KMP.make_useful()
        self.setMinimumSize(200,200)

        self.undo_history: list[UndoEntry] = []
        self.redo_history: list[UndoEntry] = []

        try:
            self.configuration = read_config()
            print("Config file loaded")
        except FileNotFoundError as e:
            print("No config file found, creating default config...")
            self.configuration = make_default_config()

        self.pathsconfig = self.configuration["default paths"]
        self.editorconfig = self.configuration["editor"]
        self.current_gen_path = None

        self.setup_ui()

        self.level_view.level_file = self.level_file
        self.level_view.set_editorconfig(self.configuration["editor"])
        self.level_view.visibility_menu = self.visibility_menu
        self.collision_area_dialog = None
        self.variants = None

        self.current_coordinates = None
        self.editing_windows = {}
        self.add_object_window = AddPikObjectWindow(self)
        self.add_object_window.setWindowIcon(self.windowIcon())
        self.object_to_be_added = None

        self.edit_spawn_window = None

        self._window_title = ""
        self._user_made_change = False
        self._justupdatingselectedobject = False

        self.loaded_archive = None
        self.loaded_archive_file = None
        self.last_position_clicked = []

        self.connect_start = None
        self.ready_to_connect = False

        self._dontselectfromtree = False

        #self.dolphin = Game()
        #self.level_view.dolphin = self.dolphin
        self.last_chosen_type = ""
        
        self.first_time_3dview = True
        
        self.restore_geometry()
        
        self.obj_to_copy = None
        self.objs_to_copy = None
        self.points_added = 0
        
        with open ("toadette.qss") as f:
            lines = f.read()
            lines = lines.strip()
            self.setStyleSheet(lines)
        self.leveldatatreeview.set_objects(self.level_file)    
        self.leveldatatreeview.bound_to_group(self.level_file)
        self.level_view.do_redraw()
        
        self.update_3d()

        self.undo_history.append(self.generate_undo_entry())

    def save_geometry(self):
        if "geometry" not in self.configuration:
            self.configuration["geometry"] = geo_config = {}
        else:
            geo_config = self.configuration["geometry"]

        def to_base64(byte_array: QtCore.QByteArray) -> str:
            return bytes(byte_array.toBase64()).decode(encoding='ascii')

        geo_config["window_geometry"] = to_base64(self.saveGeometry())
        geo_config["window_state"] = to_base64(self.saveState())
        geo_config["window_splitter"] = to_base64(self.horizontalLayout.saveState())

        if self.collision_area_dialog is not None:
            geo_config["collision_window_geometry"] = to_base64(
                self.collision_area_dialog.saveGeometry())

        save_cfg(self.configuration)

    def restore_geometry(self):
        if "geometry" not in self.configuration:
            return
        geo_config = self.configuration["geometry"]

        def to_byte_array(byte_array: str) -> QtCore.QByteArray:
            return QtCore.QByteArray.fromBase64(byte_array.encode(encoding='ascii'))

        self.restoreGeometry(to_byte_array(geo_config["window_geometry"]))
        self.restoreState(to_byte_array(geo_config["window_state"]))
        self.horizontalLayout.restoreState(to_byte_array(geo_config["window_splitter"]))

    def closeEvent(self, event: QtGui.QCloseEvent):
        self.save_geometry()

        super().closeEvent(event)

    @catch_exception
    def reset(self):
        self.last_position_clicked = []
        self.loaded_archive = None
        self.loaded_archive_file = None
        self.object_to_be_added = None
        self.level_view.reset(keep_collision=True)

        self.current_coordinates = None
        for key, val in self.editing_windows.items():
            val.destroy()

        self.editing_windows = {}

        if self.edit_spawn_window is not None:
            self.edit_spawn_window.destroy()
            self.edit_spawn_window = None

        self.current_gen_path = None
        self.pik_control.reset_info()
        self.pik_control.button_add_object.setChecked(False)
        #self.pik_control.button_move_object.setChecked(False)
        self._window_title = ""
        self._user_made_change = False
        
        self.points_added = 0

    def set_base_window_title(self, name):
        self._window_title = name
        if name != "":
            self.setWindowTitle("gcn kmp editor (demake) - "+name)
        else:
            self.setWindowTitle("gcn kmp editor (demake)")

    def set_has_unsaved_changes(self, hasunsavedchanges):
        if hasunsavedchanges and not self._user_made_change:
            self._user_made_change = True

            if self._window_title != "":
                self.setWindowTitle("gcn kmp editor (demake) [Unsaved Changes] - " + self._window_title)
            else:
                self.setWindowTitle("gcn kmp editor (demake) [Unsaved Changes] ")
        elif not hasunsavedchanges and self._user_made_change:
            self._user_made_change = False
            if self._window_title != "":
                self.setWindowTitle("gcn kmp editor (demake) - " + self._window_title)
            else:
                self.setWindowTitle("gcn kmp editor (demake)")

    def generate_undo_entry(self) -> UndoEntry:
        bol_document = self.level_file.to_bytes()

        # List containing a tuple with the emptiness and ID of each of the enemy paths.
        enemy_paths = self.level_file.enemypointgroups.groups
        enemy_path_data = tuple((not path.points, path.id) for path in enemy_paths)

        return UndoEntry(bol_document, enemy_path_data)



    def load_top_undo_entry(self):
        if not self.undo_history:
            return

        current_undo_entry = self.generate_undo_entry()
        undo_entry = self.undo_history[-1]

        bol_changed = current_undo_entry.bol_hash != undo_entry.bol_hash

        self.level_file = KMP.from_bytes(undo_entry.bol_document)

        # The BOL document cannot store information on empty enemy paths; this information is
        # sourced from a separate list.
        bol_enemy_paths = list(self.level_file.enemypointgroups.groups)
        self.level_file.enemypointgroups.groups.clear()
        enemy_path_data = undo_entry.enemy_path_data
        for empty, enemy_path_id in enemy_path_data:
            if empty:
                empty_enemy_path = libkmp.EnemyPointGroup()
                empty_enemy_path.id = enemy_path_id
                self.level_file.enemypointgroups.groups.append(empty_enemy_path)
            else:
                enemy_path = bol_enemy_paths.pop(0)
                assert enemy_path.id == enemy_path_id
                self.level_file.enemypointgroups.groups.append(enemy_path)

        self.level_view.level_file = self.level_file
        self.leveldatatreeview.set_objects(self.level_file)

        self.update_3d()
        self.pik_control.update_info()

        if bol_changed:
            self.set_has_unsaved_changes(True)
            self.error_analyzer_button.analyze_bol(self.level_file)

    def on_undo_action_triggered(self):
        if len(self.undo_history) > 1:
            self.redo_history.insert(0, self.undo_history.pop())
            self.update_undo_redo_actions()
            self.load_top_undo_entry()

    def on_redo_action_triggered(self):
        if self.redo_history:
            self.undo_history.append(self.redo_history.pop(0))
            self.update_undo_redo_actions()
            self.load_top_undo_entry()

    def on_document_potentially_changed(self, update_unsaved_changes=True):
        undo_entry = self.generate_undo_entry()

        if self.undo_history[-1] != undo_entry:
            bol_changed = self.undo_history[-1].bol_hash != undo_entry.bol_hash

            self.undo_history.append(undo_entry)
            self.redo_history.clear()
            self.update_undo_redo_actions()

            if bol_changed:
                if update_unsaved_changes:
                    self.set_has_unsaved_changes(True)

                self.error_analyzer_button.analyze_bol(self.level_file)

    def update_undo_redo_actions(self):
        self.undo_action.setEnabled(len(self.undo_history) > 1)
        self.redo_action.setEnabled(bool(self.redo_history))

    @catch_exception_with_dialog
    def do_goto_action(self, item, index):
        _ = index
        self.tree_select_object(item)
        self.frame_selection(adjust_zoom=False)
        
    def frame_selection(self, adjust_zoom):
        selected_only = bool(self.level_view.selected_positions)
        minx, miny, minz, maxx, maxy, maxz = self.compute_objects_extent(selected_only)

        # Center of the extent.
        x = (maxx + minx) / 2
        y = (maxy + miny) / 2
        z = (maxz + minz) / 2

        if self.level_view.mode == MODE_TOPDOWN:
            self.level_view.offset_z = -z
            self.level_view.offset_x = -x

            if adjust_zoom:
                if self.level_view.canvas_width > 0 and self.level_view.canvas_height > 0:
                    MARGIN = 2000
                    deltax = maxx - minx + MARGIN
                    deltay = maxz - minz + MARGIN
                    hzoom = deltax / self.level_view.canvas_width * 10
                    vzoom = deltay / self.level_view.canvas_height * 10
                    DEFAULT_ZOOM = 80
                    self.level_view._zoom_factor = max(hzoom, vzoom, DEFAULT_ZOOM)
        else:
            look = self.level_view.camera_direction.copy()

            if adjust_zoom:
                MARGIN = 3000
                deltax = maxx - minx + MARGIN
                fac = deltax
            else:
                fac = 5000

            self.level_view.offset_z = -(z + look.y * fac)
            self.level_view.offset_x = x - look.x * fac
            self.level_view.camera_height = y - look.z * fac

        self.level_view.do_redraw()

    def compute_objects_extent(self, selected_only):
        extent = []

        def extend(position):
            if not extent:
                extent.extend([position.x, position.y, position.z,
                               position.x, position.y, position.z])
                return

            extent[0] = min(extent[0], position.x)
            extent[1] = min(extent[1], position.y)
            extent[2] = min(extent[2], position.z)
            extent[3] = max(extent[3], position.x)
            extent[4] = max(extent[4], position.y)
            extent[5] = max(extent[5], position.z)

        if selected_only:
            for selected_position in self.level_view.selected_positions:
                extend(selected_position)
            return tuple(extent) or (0, 0, 0, 0, 0, 0)

        if self.visibility_menu.enemyroute.is_visible():
            for enemy_path in self.level_file.enemypointgroups.groups:
                for enemy_path_point in enemy_path.points:
                    extend(enemy_path_point.position)
        if self.visibility_menu.itemroute.is_visible():
            for item_path in self.level_file.itempointgroups.groups:
                for item_path_point in item_path.points:
                    extend(item_path_point.position)

        if self.visibility_menu.objectroutes.is_visible():
            for object_route in self.level_file.routes:
                for object_route_point in object_route.points:
                    extend(object_route_point.position)
        if self.visibility_menu.cameraroutes.is_visible():
            for object_route in self.level_file.cameraroutes:
                for object_route_point in object_route.points:
                    extend(object_route_point.position)
        if self.visibility_menu.checkpoints.is_visible():
            for checkpoint_group in self.level_file.checkpoints.groups:
                for checkpoint in checkpoint_group.points:
                    extend(checkpoint.start)
                    extend(checkpoint.end)
        if self.visibility_menu.objects.is_visible():
            for object_ in self.level_file.objects.objects:
                extend(object_.position)
        if self.visibility_menu.areas.is_visible():
            for area in self.level_file.areas.areas:
                extend(area.position)
        if self.visibility_menu.cameras.is_visible():
            for camera in self.level_file.cameras:
                extend(camera.position)
        if self.visibility_menu.respawnpoints.is_visible():
            for respawn_point in self.level_file.respawnpoints:
                extend(respawn_point.position)
        if self.visibility_menu.kartstartpoints.is_visible():
            for karts_point in self.level_file.kartpoints.positions:
                extend(karts_point.position)

        if self.visibility_menu.cannonpoints.is_visible():
            for karts_point in self.level_file.cannonpoints:
                extend(karts_point.position)

        if self.visibility_menu.missionpoints.is_visible():
            for karts_point in self.level_file.missionpoints:
                extend(karts_point.position)

        return tuple(extent) or (0, 0, 0, 0, 0, 0)

    def tree_select_arrowkey(self):
        current = self.leveldatatreeview.selectedItems()
        if len(current) == 1:
            self.tree_select_object(current[0])

    def tree_select_object(self, item):
        """if self._dontselectfromtree:
            #print("hmm")
            #self._dontselectfromtree = False
            return"""

        #print("Selected kmp editor:", item)
        self.level_view.selected = []
        self.level_view.selected_positions = []
        self.level_view.selected_rotations = []

        if isinstance(item, (tree_view.CameraEntry, tree_view.RespawnEntry, tree_view.AreaEntry, tree_view.ObjectEntry,
                             tree_view.KartpointEntry, tree_view.EnemyRoutePoint, tree_view.ItemRoutePoint,
                             tree_view.ObjectRoutePoint, tree_view.CameraRoutePoint,
                             tree_view.CannonEntry, tree_view.MissionEntry)):
            bound_to = item.bound_to
            self.level_view.selected = [bound_to]
            self.level_view.selected_positions = [bound_to.position]

            if hasattr(bound_to, "rotation"):
                self.level_view.selected_rotations = [bound_to.rotation]

        elif isinstance(item, tree_view.Checkpoint):
            bound_to = item.bound_to
            self.level_view.selected = [bound_to]
            self.level_view.selected_positions = [bound_to.start, bound_to.end]
        elif isinstance(item, (tree_view.EnemyPointGroup, tree_view.ItemPointGroup, tree_view.CheckpointGroup, tree_view.ObjectPointGroup, tree_view.CameraPointGroup)):
            self.level_view.selected = [item.bound_to]
        elif isinstance(item, tree_view.KMPHeader) and self.level_file is not None:
            self.level_view.selected = [self.level_file]

        self.pik_control.set_buttons(item)

        self.level_view.gizmo.move_to_average(self.level_view.selected_positions)
        self.level_view.do_redraw()
        self.level_view.select_update.emit()

    def setup_ui(self):
        self.resize(3000, 2000)
        self.set_base_window_title("")

        self.setup_ui_menubar()
        self.setup_ui_toolbar()

        #self.centralwidget = QWidget(self)
        #self.centralwidget.setObjectName("centralwidget")

        self.horizontalLayout = QSplitter()
        self.centralwidget = self.horizontalLayout
        self.setCentralWidget(self.horizontalLayout)
        self.leveldatatreeview = LevelDataTreeView(self.centralwidget)
        #self.leveldatatreeview.itemClicked.connect(self.tree_select_object)
        self.leveldatatreeview.itemDoubleClicked.connect(self.do_goto_action)
        self.leveldatatreeview.itemSelectionChanged.connect(self.tree_select_arrowkey)

        self.level_view = KMPMapViewer(int(self.editorconfig.get("multisampling", 8)),
                                       self.centralwidget)

        self.horizontalLayout.setObjectName("horizontalLayout")
        self.horizontalLayout.addWidget(self.leveldatatreeview)
        self.horizontalLayout.addWidget(self.level_view)
        self.leveldatatreeview.resize(200, self.leveldatatreeview.height())
        #self.leveldatatreeview.resize(200, 2500)
        spacerItem = QSpacerItem(10, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        #self.horizontalLayout.addItem(spacerItem)

        self.pik_control = PikminSideWidget(self)
        self.horizontalLayout.addWidget(self.pik_control)

        QtWidgets.QShortcut(Qt.Key_G, self).activated.connect(self.action_ground_objects)
        #QtWidgets.QShortcut(Qt.CTRL + Qt.Key_A, self).activated.connect(self.shortcut_open_add_item_window)
        self.statusbar = QStatusBar(self)
        self.statusbar.setObjectName("statusbar")
        self.setStatusBar(self.statusbar)

        self.error_analyzer_button = ErrorAnalyzerButton()
        self.error_analyzer_button.clicked.connect(lambda _checked: self.analyze_for_mistakes())
        self.statusbar.addPermanentWidget(self.error_analyzer_button)

        self.connect_actions()

    @catch_exception_with_dialog
    def setup_ui_menubar(self):
        self.menubar = QMenuBar(self)
        self.file_menu = QMenu(self)
        self.file_menu.setTitle("File")

        save_file_shortcut = QtWidgets.QShortcut(Qt.CTRL + Qt.Key_S, self.file_menu)
        save_file_shortcut.activated.connect(self.button_save_level)
        #QtWidgets.QShortcut(Qt.CTRL + Qt.Key_O, self.file_menu).activated.connect(self.button_load_level)
        #QtWidgets.QShortcut(Qt.CTRL + Qt.Key_Alt + Qt.Key_S, self.file_menu).activated.connect(self.button_save_level_as)

        self.file_load_action = QAction("Load", self)
        self.file_load_recent_menu = QMenu("Load Recent", self)
        self.save_file_action = QAction("Save", self)
        self.save_file_as_action = QAction("Save As", self)
        self.save_file_action.setShortcut("Ctrl+S")
        self.file_load_action.setShortcut("Ctrl+O")
        self.save_file_as_action.setShortcut("Ctrl+Alt+S")

        self.save_file_copy_as_action = QAction("Save Copy As", self)

        self.file_load_action.triggered.connect(self.button_load_level)
        self.save_file_action.triggered.connect(self.button_save_level)
        self.save_file_as_action.triggered.connect(self.button_save_level_as)
        self.save_file_copy_as_action.triggered.connect(self.button_save_level_copy_as)


        self.file_menu.addAction(self.file_load_action)
        self.file_menu.addMenu(self.file_load_recent_menu)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.save_file_action)
        self.file_menu.addAction(self.save_file_as_action)
        self.file_menu.addAction(self.save_file_copy_as_action)
        
        self.file_menu.aboutToShow.connect(self.on_file_menu_aboutToShow)

        self.edit_menu = QMenu(self)
        self.edit_menu.setTitle("Edit")
        self.undo_action = self.edit_menu.addAction('Undo')
        self.undo_action.setShortcut(QtGui.QKeySequence('Ctrl+Z'))
        self.undo_action.triggered.connect(self.on_undo_action_triggered)
        self.redo_action = self.edit_menu.addAction('Redo')
        self.redo_action.setShortcuts([
            QtGui.QKeySequence('Ctrl+Shift+Z'),
            QtGui.QKeySequence('Ctrl+Y'),
        ])
        self.redo_action.triggered.connect(self.on_redo_action_triggered)
        self.update_undo_redo_actions()

        self.edit_menu.addSeparator()
        self.cut_action = self.edit_menu.addAction("Cut")
        self.cut_action.setShortcut(QtGui.QKeySequence('Ctrl+X'))
        self.cut_action.triggered.connect(self.on_cut_action_triggered)
        self.copy_action = self.edit_menu.addAction("Copy")
        self.copy_action.setShortcut(QtGui.QKeySequence('Ctrl+C'))
        self.copy_action.triggered.connect(self.on_copy_action_triggered)

        self.copy_and_place_action = self.edit_menu.addAction("Copy and Place")
        self.copy_and_place_action.setShortcut(QtGui.QKeySequence('Ctrl+Shift+C'))
        self.copy_and_place_action.triggered.connect(self.set_and_start_copying)

        self.paste_action = self.edit_menu.addAction("Paste")
        self.paste_action.setShortcut(QtGui.QKeySequence('Ctrl+V'))
        self.paste_action.triggered.connect(self.on_paste_action_triggered)

        self.visibility_menu = mkwii_widgets.FilterViewMenu(self)
        self.visibility_menu.filter_update.connect(self.on_filter_update)
        filters = self.editorconfig["filter_view"].split(",")
        for object_toggle in self.visibility_menu.get_entries():
            if object_toggle.action_view_toggle.text() in filters:
                object_toggle.action_view_toggle.blockSignals(True)
                object_toggle.action_view_toggle.setChecked(False)
                object_toggle.action_view_toggle.blockSignals(False)
            if object_toggle.action_select_toggle.text() in filters:
                object_toggle.action_select_toggle.blockSignals(True)
                object_toggle.action_select_toggle.setChecked(False)
                object_toggle.action_select_toggle.blockSignals(False)

        # ------ Collision Menu
        self.collision_menu = QMenu(self.menubar)
        self.collision_menu.setTitle("Geometry")
        self.collision_load_action = QAction("Load OBJ", self)
        self.collision_load_action.triggered.connect(self.button_load_collision)
        self.collision_menu.addAction(self.collision_load_action)
        self.collision_load_grid_action = QAction("Load KCL", self)
        self.collision_load_grid_action.triggered.connect(self.button_load_collision_kcl)
        self.collision_menu.addAction(self.collision_load_grid_action)

        self.collision_menu.addSeparator()

        self.choose_bco_area = QAction("Collision Areas (KCL)")
        self.choose_bco_area.triggered.connect(self.action_choose_kcl_flag)
        self.collision_menu.addAction(self.choose_bco_area)
        self.choose_bco_area.setShortcut("Ctrl+3")

        # Misc
        self.misc_menu = QMenu(self.menubar)
        self.misc_menu.setTitle("Misc")
        #self.spawnpoint_action = QAction("Set startPos/Dir", self)
        #self.spawnpoint_action.triggered.connect(self.action_open_rotationedit_window)
        #self.misc_menu.addAction(self.spawnpoint_action)
        self.rotation_mode = QAction("Rotate Positions around Pivot", self)
        self.rotation_mode.setCheckable(True)
        self.rotation_mode.setChecked(True)
        #self.goto_action.triggered.connect(self.do_goto_action)
        #self.goto_action.setShortcut("Ctrl+G")
        
        self.frame_action = QAction("Frame Selection/All", self)
        self.frame_action.triggered.connect(
            lambda _checked: self.frame_selection(adjust_zoom=True))
        self.frame_action.setShortcut("F")
        
        self.misc_menu.addAction(self.rotation_mode)
        self.misc_menu.addAction(self.frame_action)
        self.analyze_action = QAction("Analyze for common mistakes", self)
        self.analyze_action.triggered.connect(self.analyze_for_mistakes)
        self.misc_menu.addAction(self.analyze_action)
        
        
        self.misc_menu.aboutToShow.connect(
            lambda: self.frame_action.setText(
                "Frame Selection" if self.level_view.selected_positions else "Frame All"))

        self.view_action_group = QtWidgets.QActionGroup(self)

        self.change_to_topdownview_action = QAction("Topdown View", self)
        self.view_action_group.addAction(self.change_to_topdownview_action)
        self.change_to_topdownview_action.triggered.connect(self.change_to_topdownview)
        self.misc_menu.addAction(self.change_to_topdownview_action)
        self.change_to_topdownview_action.setCheckable(True)
        self.change_to_topdownview_action.setChecked(True)
        self.change_to_topdownview_action.setShortcut("Ctrl+1")

        self.change_to_3dview_action = QAction("3D View", self)
        self.view_action_group.addAction(self.change_to_3dview_action)
        self.change_to_3dview_action.triggered.connect(self.change_to_3dview)
        self.misc_menu.addAction(self.change_to_3dview_action)
        self.change_to_3dview_action.setCheckable(True)
        self.change_to_3dview_action.setShortcut("Ctrl+2")
        
        self.do_auto_qol = QAction("Run Auto QOL")
        self.do_auto_qol.triggered.connect(self.auto_qol)
        self.misc_menu.addAction(self.do_auto_qol)
        self.do_auto_qol.setShortcut("Ctrl+4")

        self.menubar.addAction(self.file_menu.menuAction())
        self.menubar.addAction(self.edit_menu.menuAction())
        self.menubar.addAction(self.visibility_menu.menuAction())
        self.menubar.addAction(self.collision_menu.menuAction())
        self.menubar.addAction(self.misc_menu.menuAction())
        
        self.setMenuBar(self.menubar)

        self.last_obj_select_pos = 0

    def action_choose_kcl_flag(self):
        if not isinstance(self.level_view.alternative_mesh, CollisionModel):
            QtWidgets.QMessageBox.information(self, "Collision Areas (KCL)",
                                              "No collision file is loaded.")
            return

        if self.collision_area_dialog is not None:
            self.collision_area_dialog.close()
            self.collision_area_dialog = None

        collision_model = self.level_view.alternative_mesh
        colltypes = tuple(sorted(collision_model.meshes))

        if self.variants is None:
        
            with open("lib/kcl_variants.json", "r") as f:
                self.variants = json.load(f)

        #colltypes is every collision flag found
        #group based on the last five bits
        colltypegroups = {}
        for colltype in colltypes:
            colltypegroup = colltype & 0x001F
            if colltypegroup not in colltypegroups:
                colltypegroups[colltypegroup] = []
            colltypegroups[colltypegroup].append(colltype)

        class DeselectableTableWidget(QtWidgets.QTreeWidget):
            def mousePressEvent(self, event):
                super().mousePressEvent(event)

                modelIndex = self.indexAt(event.pos())
                if not modelIndex.isValid():
                    self.clearSelection()

        tree_widget = DeselectableTableWidget()
        tree_widget.setColumnCount(2)
        tree_widget.setHeaderLabels(("Basic Type", "Description"))

        def get_collision_type_desc(label):
            group_descs = {
                "0x00": "Road",
                "0x01": "Slippery Road 1",
                "0x02": "Weak Off-road",
                "0x03": "Medium Off-road",
                "0x04": "Heavy Off-road",
                "0x05": "Slippery Road 2",
                "0x06": "Boost Panel",
                "0x07": "Boost Ramp",
                "0x08": "Jump Pad",
                "0x09": "Item Road",
                "0x0A": "Solid Fall",
                "0x0B": "Moving Water",
                "0x0C": "Wall",
                "0x0D": "Invisible wall",
                "0x0E": "Item Wall",
                "0x0F": "Wall 2",
                "0x10": "Fall Boundary",
                "0x11": "Cannon Trigger",
                "0x12": "Force Recalculation",
                "0x13": "Half-pipe Ramp",
                "0x14": "Player-Only Wall",
                "0x15": "Moving Road",
                "0x16": "Sticky/Gravity Road",
                "0x17": "Road 2",
                "0x18": "Sound Trigger",
                "0x19": "Weak Wall",
                "0x1A": "Effect Trigger",
                "0x1B": "Item State Modifier",
                "0x1C": "Half-Pipe Invisible Wall",
                "0x1D": "Rotating Road",
                "0x1E": "Special Wall",
                "0x1F": "Invisible Wall 2",

            }

            return group_descs.get(label, "")

        def get_collision_other_desc(colltype):
            build_string = ""
            
            variant = (colltype & 0x00E0) >> 5
            coltype = colltype & 0x001F

            if str(coltype) in self.variants:
                build_string += ", Variant: " + self.variants[str(coltype)][variant]
            
            if (colltype & 0x2000) != 0:
                build_string += ", Trickable"

            if (colltype & 0x4000) != 0:
                build_string += ", Driveable"

            if (colltype & 0x8000) != 0:
                build_string += ", Soft Wall"

            return build_string

        for colltypegroup in sorted(colltypegroups):
            colltypes = colltypegroups[colltypegroup]

            if len(colltypes) == 1 and colltypegroup not in collision_model.hidden_collision_type_groups:
                colltype = colltypes[0]
                label = "0x{0:0{1}X}".format(colltypegroup, 2)
                tree_widget_item = QtWidgets.QTreeWidgetItem(None, (label, ))
                tree_widget_item.setData(0, QtCore.Qt.UserRole + 1, colltype)
                tree_widget_item.setData(1, QtCore.Qt.DisplayRole, get_collision_type_desc(label))
                tree_widget_item.setCheckState(
                    0, QtCore.Qt.Checked
                    if colltype not in collision_model.hidden_collision_types
                    else QtCore.Qt.Unchecked)
                tree_widget.addTopLevelItem(tree_widget_item)
                continue

            label = "0x{0:0{1}X}".format(colltypegroup, 2)
            tree_widget_item = QtWidgets.QTreeWidgetItem(None, (label, ))
            tree_widget_item.setData(0, QtCore.Qt.UserRole + 1, colltypegroup)
            tree_widget_item.setData(1, QtCore.Qt.DisplayRole, get_collision_type_desc(label))
            tree_widget_item.setCheckState(
                0, QtCore.Qt.Checked
                if colltypegroup not in collision_model.hidden_collision_type_groups
                else QtCore.Qt.Unchecked)
            tree_widget.addTopLevelItem(tree_widget_item)
            for colltype in colltypes:
                label = "0x{0:0{1}X}".format(colltype, 4)
                child_tree_widget_item = QtWidgets.QTreeWidgetItem(tree_widget_item, (label, ))
                child_tree_widget_item.setData(0, QtCore.Qt.UserRole + 1, colltype)
                child_tree_widget_item.setData(1, QtCore.Qt.DisplayRole, get_collision_other_desc(colltype))
                child_tree_widget_item.setCheckState(
                    0, QtCore.Qt.Checked
                    if colltype not in collision_model.hidden_collision_types
                    else QtCore.Qt.Unchecked)

        def on_tree_widget_itemSelectionChanged(tree_widget=tree_widget):
            self.level_view.highlight_colltype = None

            for item in tree_widget.selectedItems():
                if item.childCount():
                    continue
                self.level_view.highlight_colltype = item.data(0, QtCore.Qt.UserRole + 1)
                break

            self.update_3d()

        all_items = tree_widget.findItems(
            "*",
            QtCore.Qt.MatchWrap | QtCore.Qt.MatchWildcard
            | QtCore.Qt.MatchRecursive)

        show_all_button = QtWidgets.QPushButton('Show All')
        hide_all_button = QtWidgets.QPushButton('Hide All')

        def update_both_all_buttons():
            checked_count = 0
            for item in all_items:
                checked = item.checkState(0) == QtCore.Qt.Checked
                if checked:
                    checked_count += 1

            show_all_button.setEnabled(checked_count < len(all_items))
            hide_all_button.setEnabled(checked_count)

        #edits the configuration file
        def on_tree_widget_itemChanged(item, column, tree_widget=tree_widget):
            for item in all_items:
                checked = item.checkState(0) == QtCore.Qt.Checked
                if item.childCount():
                    target_set = collision_model.hidden_collision_type_groups
                else:
                    target_set = collision_model.hidden_collision_types
                colltype = item.data(0, QtCore.Qt.UserRole + 1)
                if checked:
                    target_set.discard(colltype)
                else:
                    target_set.add(colltype)

            update_both_all_buttons()

            self.configuration["editor"]["hidden_collision_types"] = \
                ",".join(str(t) for t in collision_model.hidden_collision_types)
            self.configuration["editor"]["hidden_collision_type_groups"] = \
                ",".join(str(t) for t in collision_model.hidden_collision_type_groups)

            save_cfg(self.configuration)
            self.update_3d()

        tree_widget.itemSelectionChanged.connect(on_tree_widget_itemSelectionChanged)
        tree_widget.itemChanged.connect(on_tree_widget_itemChanged)

        tree_widget.expandAll()
        tree_widget.resizeColumnToContents(0)

        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.setContentsMargins(5, 5, 5, 5)
        buttons_layout.setSpacing(5)
        def on_show_all_button_clicked(checked):
            for item in all_items:
                item.setCheckState(0, QtCore.Qt.Checked)
        show_all_button.clicked.connect(on_show_all_button_clicked)
        def on_hide_all_button_clicked(checked):
            for item in all_items:
                item.setCheckState(0, QtCore.Qt.Unchecked)
        hide_all_button.clicked.connect(on_hide_all_button_clicked)
        buttons_layout.addWidget(show_all_button)
        buttons_layout.addWidget(hide_all_button)
        update_both_all_buttons()

        self.collision_area_dialog = QtWidgets.QDialog(self)
        self.collision_area_dialog.setWindowTitle("Collision Areas (KCL)")
        self.collision_area_dialog.setContentsMargins(0, 0, 0, 0)
        layout = QtWidgets.QVBoxLayout(self.collision_area_dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(tree_widget)
        layout.addLayout(buttons_layout)
        
        if "geometry" in self.configuration:
            geo_config = self.configuration["geometry"]

            def to_byte_array(byte_array: str) -> QtCore.QByteArray:
                return QtCore.QByteArray.fromBase64(byte_array.encode(encoding='ascii'))

            if "collision_window_geometry" in geo_config:
                self.collision_area_dialog.restoreGeometry(
                    to_byte_array(geo_config["collision_window_geometry"]))
        
        self.collision_area_dialog.show()
        
        
        def on_dialog_finished(result):
            _ = result
            if self.isVisible():
                self.save_geometry()

        self.collision_area_dialog.finished.connect(on_dialog_finished)
        
        

    def analyze_for_mistakes(self):
        analyzer_window = ErrorAnalyzer(self.level_file, parent=self)
        analyzer_window.exec_()
        analyzer_window.deleteLater()

    
    def on_file_menu_aboutToShow(self):
        recent_files = self.get_recent_files_list()

        self.file_load_recent_menu.setEnabled(bool(recent_files))
        self.file_load_recent_menu.clear()

        for filepath in recent_files:
            recent_file_action = self.file_load_recent_menu.addAction(filepath)
            recent_file_action.triggered.connect(
                lambda checked, filepath=filepath: self.button_load_level(checked, filepath))

    def on_filter_update(self):
        filters = []
        for object_toggle in self.visibility_menu.get_entries():
            if not object_toggle.action_view_toggle.isChecked():
                filters.append(object_toggle.action_view_toggle.text())
            if not object_toggle.action_select_toggle.isChecked():
                filters.append(object_toggle.action_select_toggle.text())

        self.editorconfig["filter_view"] = ','.join(filters)
        save_cfg(self.configuration)

        self.level_view.do_redraw()

    
    def on_cull_faces_triggered(self, checked):
        self.editorconfig["cull_faces"] = "True" if checked else "False"
        save_cfg(self.configuration)

        self.level_view.cull_faces = bool(checked)
        self.level_view.do_redraw()

    def change_to_topdownview(self, checked):
        if checked:
            self.level_view.change_from_3d_to_topdown()

    def change_to_3dview(self, checked):
        if checked:
            self.level_view.change_from_topdown_to_3d()
            self.statusbar.clearMessage()
            
            # After switching to the 3D view for the first time, the view will be framed to help
            # users find the objects in the world.
            if self.first_time_3dview:
                self.first_time_3dview = False
                self.frame_selection(adjust_zoom=True)

    def setup_ui_toolbar(self):
        # self.toolbar = QtWidgets.QToolBar("Test", self)
        # self.toolbar.addAction(QAction("TestToolbar", self))
        # self.toolbar.addAction(QAction("TestToolbar2", self))
        # self.toolbar.addAction(QAction("TestToolbar3", self))

        # self.toolbar2 = QtWidgets.QToolBar("Second Toolbar", self)
        # self.toolbar2.addAction(QAction("I like cake", self))

        # self.addToolBar(self.toolbar)
        # self.addToolBarBreak()
        # self.addToolBar(self.toolbar2)
        pass

    def connect_actions(self):
        self.level_view.select_update.connect(self.action_update_info)
        self.level_view.select_update.connect(self.select_from_3d_to_treeview)
        self.level_view.select_update.connect(self.action_connectedto_final)
        #self.pik_control.lineedit_coordinatex.textChanged.connect(self.create_field_edit_action("coordinatex"))
        #self.pik_control.lineedit_coordinatey.textChanged.connect(self.create_field_edit_action("coordinatey"))
        #self.pik_control.lineedit_coordinatez.textChanged.connect(self.create_field_edit_action("coordinatez"))

        #self.pik_control.lineedit_rotationx.textChanged.connect(self.create_field_edit_action("rotationx"))
        #self.pik_control.lineedit_rotationy.textChanged.connect(self.create_field_edit_action("rotationy"))
        #self.pik_control.lineedit_rotationz.textChanged.connect(self.create_field_edit_action("rotationz"))

        self.level_view.position_update.connect(self.action_update_position)
        self.level_view.connected_to_point.connect(self.action_connectedto_end)

        self.level_view.customContextMenuRequested.connect(self.mapview_showcontextmenu)

        self.pik_control.button_add_object.clicked.connect(
            lambda _checked: self.button_open_add_item_window())
        self.pik_control.button_add_object.setShortcut("V")

        self.pik_control.button_stop_object.pressed.connect(self.button_add_item_window_close)
        self.pik_control.button_stop_object.setShortcut("T")

        #self.pik_control.button_move_object.pressed.connect(self.button_move_objects)
        self.level_view.move_points.connect(self.action_move_objects)
        self.level_view.height_update.connect(self.action_change_object_heights)
        self.level_view.create_waypoint.connect(self.action_add_object)
        self.level_view.create_waypoint_3d.connect(self.action_add_object_3d)
        self.pik_control.button_ground_object.clicked.connect(
            lambda _checked: self.action_ground_objects())
        self.pik_control.button_remove_object.clicked.connect(
            lambda _checked: self.action_delete_objects())

        delete_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(Qt.Key_Delete), self)
        delete_shortcut.activated.connect(self.action_delete_objects)


        self.level_view.rotate_current.connect(self.action_rotate_object)
        self.leveldatatreeview.select_all.connect(self.select_all_of_group)
        self.leveldatatreeview.reverse.connect(self.reverse_all_of_group)
        self.leveldatatreeview.duplicate.connect(self.duplicate_group_from_tree)
        self.leveldatatreeview.split.connect(self.split_group_from_tree)
    
    

    def split_group_from_tree(self, group_item, item):
        group = group_item.bound_to
        point = item.bound_to
        self.split_group(group, point)

    def split_group(self, group, point):
        if point == group.points[-1]:
            return
       
        # Get new hopefully unused group id
        
        to_deal_with = self.level_file.get_to_deal_with(point) 
        to_deal_with.split_group( group, point  )
       
        self.leveldatatreeview.set_objects(self.level_file)
        self.update_3d()
        self.set_has_unsaved_changes(True)


    def duplicate_group_from_tree(self, item):
        group = item.bound_to
        if not isinstance(group, PointGroup) :
            return
        self.duplicate_group(self, group)
        #make sure that a group *can* be duplicated by checking the group's next to see if all can handle another prev, and all prev to see if they can handle another next
        
        

    def duplicate_group(self, group):
        to_deal_with = self.level_file.get_to_deal_with(group) 

        if not to_deal_with.check_if_duplicate_possible(group):
            return

        new_group_id = to_deal_with.new_group_id()
        to_deal_with.groups.append( group.copy_group(new_group_id) )

        #add new links to next and prev groups
        for idx in group.prevgroup:
            if idx != -1:
                to_deal_with.groups[idx].add_new_next(new_group_id)
        for idx in group.nextgroup:
            if idx != -1:
                to_deal_with.groups[idx].add_new_prev(new_group_id)


        self.leveldatatreeview.set_objects(self.level_file)
        self.update_3d()
        self.set_has_unsaved_changes(True)

    def reverse_all_of_group(self, item):
        group = item.bound_to
        if isinstance(group, libkmp.CheckpointGroup):
            group.points.reverse()
            for point in group.points:
                start = point.start
                point.start = point.end
                point.end = start
        elif isinstance(group, (libkmp.EnemyPointGroup, libkmp.ItemPointGroup) ):
            group.points.reverse()
        elif isinstance(group, libkmp.Route):
            group.points.reverse()

        self.leveldatatreeview.set_objects(self.level_file)
        self.update_3d()

    def select_all_of_group(self, item):
        group = item.bound_to
        self.level_view.selected = []
        self.level_view.selected_positions = []
        self.level_view.selected_rotations = []
        for point in group.points:
            self.level_view.selected.append(point)

            if isinstance(group, libkmp.CheckpointGroup):
                self.level_view.selected_positions.append(point.start)
                self.level_view.selected_positions.append(point.end)
            else:
                self.level_view.selected_positions.append(point.position)
        self.update_3d()

    def action_open_rotationedit_window(self):
        if self.edit_spawn_window is None:
            self.edit_spawn_window = mkwii_widgets.SpawnpointEditor()
            self.edit_spawn_window.position.setText("{0}, {1}, {2}".format(
                self.pikmin_gen_file.startpos_x, self.pikmin_gen_file.startpos_y, self.pikmin_gen_file.startpos_z
            ))
            self.edit_spawn_window.rotation.setText(str(self.pikmin_gen_file.startdir))
            self.edit_spawn_window.closing.connect(self.action_close_edit_startpos_window)
            self.edit_spawn_window.button_savetext.clicked.connect(
                lambda _checked: self.action_save_startpos())
            self.edit_spawn_window.show()

    def update_recent_files_list(self, filepath):
        filepath = os.path.abspath(os.path.normpath(filepath))

        recent_files = self.get_recent_files_list()
        if filepath in recent_files:
            recent_files.remove(filepath)

        recent_files.insert(0, filepath)
        recent_files = recent_files[:10]

        self.configuration["recent files"] = {}
        recent_files_config = self.configuration["recent files"]

        for i, filepath in enumerate(recent_files):
            config_entry = f"file{i}"
            recent_files_config[config_entry] = filepath

    def get_recent_files_list(self):
        if "recent files" not in self.configuration:
            self.configuration["recent files"] = {}
        recent_files_config = self.configuration["recent files"]

        recent_files = []
        for i in range(10):
            config_entry = f"file{i}"
            if config_entry in recent_files_config:
                recent_files.append(recent_files_config[config_entry])

        return recent_files

    #@catch_exception
    def button_load_level(self, checked=False, filepath=None):
        _ = checked
    
        if filepath is None:
            filepath, chosentype = QFileDialog.getOpenFileName(
                self, "Open File",
                self.pathsconfig["kmp"],
                "KMP or SZS(*.kmp *.szs);;KMP files (*.kmp);;Archived files (*.szs);;All files (*)",
                self.last_chosen_type)
        else:
            chosentype = None
       
        if filepath:
            if chosentype is not None:
                self.last_chosen_type = chosentype
            print("Resetting editor")
            self.reset()
            print("Reset done")
            print("Chosen file type:", chosentype)

            with open(filepath, "rb") as f:
                try:
                    kmp_file = KMP.from_file(f)
                    self.setup_kmp_file(kmp_file, filepath)
                    self.leveldatatreeview.set_objects(kmp_file)
                    self.leveldatatreeview.bound_to_group(kmp_file)
                    self.current_gen_path = filepath

                    filepath_base = os.path.dirname(filepath)

                    collisionfile = filepath_base+"/course.kcl"
                    if os.path.exists(collisionfile):
                        self.load_collision_kcl(collisionfile)

                except Exception as error:
                    print("Error appeared while loading:", error)
                    traceback.print_exc()
                    open_error_dialog(str(error), self)

            self.update_3d()


    def load_collision_file(self, collisionfile):
        bco_coll = RacetrackCollision()
        verts = []
        faces = []

        with open(collisionfile, "rb") as f:
            bco_coll.load_file(f)

        for vert in bco_coll.vertices:
            verts.append(vert)

        for v1, v2, v3, collision_type, rest in bco_coll.triangles:
            faces.append(((v1 + 1, None), (v2 + 1, None), (v3 + 1, None), collision_type))
        model = CollisionModel(bco_coll)
        self.setup_collision(verts, faces, collisionfile, alternative_mesh=model)

    def setup_kmp_file(self, bol_file, filepath):
        self.level_file = bol_file
        self.level_view.level_file = self.level_file
        # self.pikmin_gen_view.update()
        self.level_view.do_redraw()

        self.on_document_potentially_changed(update_unsaved_changes=False)

        print("File loaded")
        # self.bw_map_screen.update()
        # path_parts = path.split(filepath)
        self.set_base_window_title(filepath)
        self.pathsconfig["kmp"] = filepath
        self.update_recent_files_list(filepath)
        save_cfg(self.configuration)
        self.current_gen_path = filepath

    @catch_exception_with_dialog
    def button_save_level(self, *args, **kwargs):
        if self.current_gen_path is not None:
            if self.loaded_archive is not None:
                assert self.loaded_archive_file is not None
                root_name = self.loaded_archive.root.name
                file = self.loaded_archive[root_name + "/" + self.loaded_archive_file]
                file.seek(0)

                self.level_file.write(file)

                with open(self.current_gen_path, "wb") as f:
                    self.loaded_archive.write_arc(f)

                self.set_has_unsaved_changes(False)
                self.statusbar.showMessage("Saved to {0}".format(self.current_gen_path))

            else:
                gen_path = self.current_gen_path[:-3] + "backup.kmp"
                with open(gen_path, "wb") as f:
                    self.level_file.write(f)
                    self.set_has_unsaved_changes(False)

                    self.statusbar.showMessage("Saved to {0}".format(gen_path))
        else:
            self.button_save_level_as()

    def button_save_level_as(self, *args, **kwargs):
        self._button_save_level_as(True, *args, **kwargs)

    def button_save_level_copy_as(self, *args, **kwargs):
        self._button_save_level_as(False, *args, **kwargs)

    @catch_exception_with_dialog
    def _button_save_level_as(self, modify_current_path, *args, **kwargs):
        filepath, choosentype = QFileDialog.getSaveFileName(
            self, "Save File",
            self.pathsconfig["kmp"],
            "MKWii Track Data (*.kmp);;All files (*)",
            self.last_chosen_type)

        if filepath:
            if choosentype == "Archived files (*.arc)" or filepath.endswith(".arc"):
                if self.loaded_archive is None or self.loaded_archive_file is None:
                    with open(filepath, "rb") as f:
                        self.loaded_archive = Archive.from_file(f)

                self.loaded_archive_file = find_file(self.loaded_archive.root, "_course.bol")
                root_name = self.loaded_archive.root.name
                file = self.loaded_archive[root_name + "/" + self.loaded_archive_file]
                file.seek(0)

                self.level_file.write(file)

                with open(filepath, "wb") as f:
                    self.loaded_archive.write_arc(f)

                self.set_has_unsaved_changes(False)
                self.statusbar.showMessage("Saved to {0}".format(filepath))
            else:
                with open(filepath, "wb") as f:
                    self.level_file.write(f)

                    self.set_has_unsaved_changes(False)

            self.pathsconfig["kmp"] = filepath
            save_cfg(self.configuration)

            if modify_current_path:
                self.current_gen_path = filepath
                self.set_base_window_title(filepath)

            self.statusbar.showMessage("Saved to {0}".format(filepath))

    def button_load_collision(self):
        try:
            filepath, choosentype = QFileDialog.getOpenFileName(
                self, "Open File",
                self.pathsconfig["collision"],
                "Collision (*.obj);;All files (*)")

            if not filepath:
                return

            with open(filepath, "r") as f:
                faces = py_obj.read_obj(f)
            alternative_mesh = TexturedModel.from_obj_path(filepath, rotate=True)


            self.setup_collision(faces, filepath, alternative_mesh)

        except Exception as e:
            traceback.print_exc()
            open_error_dialog(str(e), self)
        finally:
            self.update_3d()

    def button_load_collision_kcl(self):
        try:
            filepath, choosentype = QFileDialog.getOpenFileName(
                self, "Open File",
                self.pathsconfig["collision"],
                "MKWII Collision (*.kcl);;All files (*)")
            if filepath:
                self.load_collision_kcl(filepath)

        except Exception as e:
            traceback.print_exc()
            open_error_dialog(str(e), self)
        finally:
            self.update_3d()

    def load_collision_kcl(self, filepath):
        kcl_coll = RacetrackCollision()
        faces = []

        
        with open(filepath, "rb") as f:
            kcl_coll.load_file(f)

        #these are the actual vertices

        #for v1, v2, v3, collision_type in kcl_coll.triangles:
        #    faces.append((v1, v2, v3, collision_type))
        faces = kcl_coll.triangles

        model = CollisionModel(kcl_coll)
        self.setup_collision(faces, filepath, alternative_mesh=model)

    def clear_collision(self):
        self.level_view.clear_collision()

        # Synchronously force a draw operation to provide immediate feedback.
        self.level_view.update()
        QApplication.instance().processEvents()

    def setup_collision(self, faces, filepath, alternative_mesh=None):
        self.level_view.set_collision(faces, alternative_mesh)
        self.pathsconfig["collision"] = filepath
        editor_config = self.configuration["editor"]
        alternative_mesh.hidden_collision_types = \
            set(int(t) for t in editor_config.get("hidden_collision_types", "").split(",") if t)
        alternative_mesh.hidden_collision_type_groups = \
            set(int(t) for t in editor_config.get("hidden_collision_type_groups", "").split(",") if t)
        save_cfg(self.configuration)

    def action_close_edit_startpos_window(self):
        self.edit_spawn_window.destroy()
        self.edit_spawn_window = None

    @catch_exception_with_dialog
    def action_save_startpos(self):
        pos, direction = self.edit_spawn_window.get_pos_dir()
        self.pikmin_gen_file.startpos_x = pos[0]
        self.pikmin_gen_file.startpos_y = pos[1]
        self.pikmin_gen_file.startpos_z = pos[2]
        self.pikmin_gen_file.startdir = direction

        #self.pikmin_gen_view.update()
        self.pikmin_gen_view.do_redraw()
        self.set_has_unsaved_changes(True)

    def button_open_add_item_window(self):
        obj = None
        add_something = False
        if len(self.level_view.selected) == 1:
            obj = self.level_view.selected[0]
        else:
            obj = self.leveldatatreeview.currentItem().bound_to
        #add points to group at current position
        if isinstance(obj, KMPPoint):
            add_something = True
            self.button_add_from_addi_options( 11, obj)
        elif isinstance(obj, PointGroup):
            add_something = True
            self.button_add_from_addi_options( 1, obj)
        elif isinstance(obj, PointGroups):
            add_something = True
            self.button_add_from_addi_options( 0, obj)

        if add_something:
            return

        accepted = self.add_object_window.exec_()
        if accepted:
            self.add_item_window_save()
        else:
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_NONE)
            self.pik_control.button_add_object.setChecked(False)

    def shortcut_open_add_item_window(self):
        self.button_open_add_item_window()

    def select_tree_item_bound_to(self, obj):
        # Iteratively traverse all the tree widget items.
        pending_items = [self.leveldatatreeview.invisibleRootItem()]
        while pending_items:
            item = pending_items.pop(0)
            for child_index in range(item.childCount()):
                child_item = item.child(child_index)

                # Check whether the item contains any item that happens to be bound to the target
                # object.
                bound_item = get_treeitem(child_item, obj)
                if bound_item is not None:
                    # If found, deselect current selection, and select the new item.
                    for selected_item in self.leveldatatreeview.selectedItems():
                        selected_item.setSelected(False)
                    bound_item.setSelected(True)

                    # Ensure that the new item is visible.
                    parent_item = bound_item.parent()
                    while parent_item is not None:
                        parent_item.setExpanded(True)
                        parent_item = parent_item.parent()
                    self.leveldatatreeview.scrollToItem(bound_item)

                    return
                else:
                    pending_items.append(child_item)

    def add_item_window_save(self):
        self.object_to_be_added = self.add_object_window.get_content()
        if self.object_to_be_added is None:
            return
        obj = self.object_to_be_added[0]

        if isinstance(obj, (libkmp.EnemyPointGroup, libkmp.CheckpointGroup, libkmp.Route) ):
            obj = deepcopy(obj)




            if isinstance(obj, libkmp.EnemyPointGroup):
                self.level_file.enemypointgroups.groups.append(obj)
            elif isinstance(obj, libkmp.CheckpointGroup):
                self.level_file.checkpoints.groups.append(obj)
            elif isinstance(obj, libkmp.Route):
                if obj.type == 0:
                    self.level_file.routes.append(obj)
                elif obj.type == 1:
                    self.level_file.cameraroutes.append(obj)

            self.object_to_be_added = None
            self.pik_control.button_add_object.setChecked(False)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_NONE)
            self.leveldatatreeview.set_objects(self.level_file)

            self.select_tree_item_bound_to(obj)

        elif self.object_to_be_added is not None:
            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)



    #this is what happens when you close out of the window
    @catch_exception
    def button_add_item_window_save(self):
        #print("ohai")
        if self.add_object_window is not None:
            self.object_to_be_added = self.add_object_window.get_content()
            print(self.object_to_be_added)
            if self.object_to_be_added is None:
                return

            obj = self.object_to_be_added[0]
            self.points_added = 0
            if isinstance(obj, (libkmp.PointGroup, libkmp.Route )):
                if isinstance(obj, libkmp.EnemyPointGroup):
                    self.level_file.enemypointgroups.groups.append(obj)
                elif isinstance(obj, libkmp.ItemPointGroup):
                    self.level_file.itempointgroups.groups.append(obj)
                elif isinstance(obj, libkmp.CheckpointGroup):
                    self.level_file.checkpoints.groups.append(obj)
                elif isinstance(obj, libkmp.Route):
                    if obj.type == 0:
                        self.level_file.routes.append(obj)
                    elif obj.type == 1:
                         self.level_file.cameraroutes.append(obj)


                self.addobjectwindow_last_selected_category = self.add_object_window.category_menu.currentIndex()
                self.object_to_be_added = None
                self.add_object_window.destroy()
                self.add_object_window = None
                self.leveldatatreeview.set_objects(self.level_file)

            elif self.object_to_be_added is not None:
                self.addobjectwindow_last_selected_category = self.add_object_window.category_menu.currentIndex()

                
                self.pik_control.button_add_object.setChecked(True)
                #self.pik_control.button_move_object.setChecked(False)
                self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)
                self.add_object_window.destroy()
                self.add_object_window = None
                #self.pikmin_gen_view.setContextMenuPolicy(Qt.DefaultContextMenu)

    @catch_exception
    def button_add_item_window_close(self):
        self.points_added = 0
        self.add_object_window = None
        copy_current_obj = None
        self.pik_control.button_add_object.setChecked(False)
        self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_NONE)
        self.objects_to_be_added = None
        self.object_to_be_added = None
    
    #this is the function that the new side buttons calls
    @catch_exception
    def button_add_from_addi_options(self, option, obj = None):
        self.points_added = 0
        copy_current_obj = None
        self.pik_control.button_add_object.setChecked(False)
        self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_NONE)
        self.objects_to_be_added = None
        self.object_to_be_added = None
        
        
        if option == 0: #add an empty enemy group
            to_deal_with = self.level_file.get_to_deal_with(obj)
            to_deal_with.add_new_group()
            """
            if isinstance(obj, (EnemyPointGroups, EnemyPointGroup)):
                new_enemy_group = libkmp.EnemyPointGroup()
                new_enemy_group.id = self.level_file.enemypointgroups.new_group_id()
                self.level_file.enemypointgroups.groups.append( new_enemy_group )

            if isinstance(obj, (ItemPointGroups, ItemPointGroup)):
                new_item_group = libkmp.ItemPointGroup()
                new_item_group.id = self.level_file.itempointgroups.new_group_id()
                self.level_file.itempointgroups.groups.append( new_item_group )"""
        elif option == 1: #adding an enemy point to a group, the group is obj
            to_deal_with = self.level_file.get_to_deal_with(obj)
            thing_to_add = to_deal_with.get_new_point()
            self.object_to_be_added = [thing_to_add, obj.id, -1 ]
            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)
        elif option == 3: #add item box
            #self.addobjectwindow_last_selected_category = 6

            default_item_box = libkmp.MapObject.new(obj)
            self.object_to_be_added = [default_item_box, None, None ]

            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)
        elif option == 4:   #generic copy
            #self.addobjectwindow_last_selected_category = 6
            self.objects_to_be_added = []
            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)
            
            self.obj_to_copy = obj
            self.copy_current_obj()
        elif option == 4.5:  #copy with new route
        
            self.objects_to_be_added = []
            self.object_to_be_added = None
            
            new_route = libkmp.Route()    
            
            to_append_to = self.level_file.routes if isinstance(obj, libkmp.MapObject) else self.level_file.cameraroutes
            new_route.type = 1 if isinstance(obj, libkmp.Camera) else 0

            if obj.route != -1 :
                for point in to_append_to[obj.route].points: 
                    new_point = libkmp.RoutePoint.new()
                    new_point.position = point.position - obj.position
                    new_point.partof = new_route
                    new_route.points.append(new_point)
            else:
                for i in range(2):
                    point = libkmp.RoutePoint.new()
                    point.partof = new_route
                    new_route.points.append(point)
            
            self.objects_to_be_added.append( [new_route, None, None ]  )
            
            if isinstance(obj, libkmp.Camera):
                new_camera = libkmp.Camera.default()
                self.objects_to_be_added.append( [new_camera, None, None ]  )

            elif isinstance(obj, libkmp.MapObject):
                new_object = obj.copy()
                self.objects_to_be_added.append( [new_object, None, None ]  )
                   
            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)
            
            self.object_to_be_added = None
        elif option == 5: #new object route
            new_route_group = libkmp.Route()
            self.level_file.routes.append(new_route_group)
        elif option == 5.5: #new camera route
            new_route_group = libkmp.Route.new_camera()
            self.level_file.cameraroutes.append(new_route_group)
        elif option == 6: #add route point
            #find route in routepoints
            id = 0
            idx = 0

            to_deal_with = self.level_file.routes if obj.type == 1 else self.level_file.cameraroutes

            for route in to_deal_with:
                if route is obj:
                    id = idx
                    break
                else:
                    idx += 1
            
            #self.addobjectwindow_last_selected_category = 5
            new_point = libkmp.RoutePoint.new()
            new_point.partof = obj
            self.object_to_be_added = [new_point, id, -1 ]

            #self.object_to_be_added[0].group = obj.id
            #actively adding objects
            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)
        elif option == 7: #add new area
            #self.addobjectwindow_last_selected_category = 7
            self.object_to_be_added = [libkmp.Area.default(obj), None, None ]
            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP) 
        elif option == 7.5: #add new type 8/9 areas
            self.objects_to_be_added = []
            self.objects_to_be_added.append( [libkmp.Area.default(8), None, None ]  )
            self.objects_to_be_added.append( [libkmp.Area.default(9), None, None ]  )
            self.object_to_be_added = None
            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP) 
        elif option == 8:  #add new camera with route
             
            if obj in [1, 3, 4, 5]:
                self.objects_to_be_added = []
                self.object_to_be_added = None

                new_route = libkmp.Route.new_camera()
                
                
                for i in range(2):
                    point = libkmp.RoutePoint.new()
                    point.partof = new_route
                    new_route.points.append(point)
                
                #self.addobjectwindow_last_selected_category = 8
                self.objects_to_be_added.append( [new_route, None, None ]  )
                self.objects_to_be_added.append( [libkmp.Camera.default(obj), None, None ] )
            else:
                self.objects_to_be_added = None
                self.object_to_be_added = [libkmp.Camera.default(obj), None, None ]
                
            
            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)
            self.object_to_be_added = None
        elif option == 9: #add new respawn point


            #self.addobjectwindow_last_selected_category = 9
            #get next id
            rsp = libkmp.JugemPoint.new()
            
            self.object_to_be_added = [rsp, None, None ]
            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)    
        elif option == 10: #merge enemy/item/route
            obj.merge_groups()       
        elif option == 11: #new enemy point here
            #find its position in the enemy point group
            to_deal_with = self.level_file.get_to_deal_with(obj)
            start_groupind, start_group, start_pointind = to_deal_with.find_group_of_point(obj)

            thing_to_add = to_deal_with.get_new_point()
            self.object_to_be_added = [thing_to_add, start_groupind, start_pointind + 1  ]
            #self.object_to_be_added[0].group = obj.id
            #actively adding objects
            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)
        elif option == 12: #area camera route add
            self.objects_to_be_added = []
            new_area = libkmp.Area.default()
            new_camera = libkmp.Camera.default()
            new_route = libkmp.Route.new_camera()
            
            for i in range(2):
                point = libkmp.RoutePoint.new()
                point.partof = new_route
                new_route.points.append(point)
                        
            self.objects_to_be_added.append( [new_route, None, None ]  )
            self.objects_to_be_added.append( [new_camera, None, None ]  )
            self.objects_to_be_added.append( [new_area, None, None ]  )    
            
                
            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)
            
            self.object_to_be_added = None
        elif option == 12.5: #area camera add
            self.objects_to_be_added = []
            new_area = libkmp.Area.default()
            new_camera = libkmp.Camera.default(1)
            
            self.objects_to_be_added.append( [new_camera, None, None ]  )
            self.objects_to_be_added.append( [new_area, None, None ]  )    
            
            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)
            
            self.object_to_be_added = None
        elif option == 15: #add new route point here
            group_id = -1
            pos_in_grp = -1 
            idx = 0

            to_deal_with = self.level_file.routes
            if obj.partof.type == 1:
                to_deal_with = self.level_file.cameraroutes

            for group_idx, group in enumerate(to_deal_with):
                for point_idx, point in enumerate(group.points):
                    if point is obj:
                        group_id = group_idx
                        pos_in_grp = point_idx
                        break

            
            self.object_to_be_added = [libkmp.RoutePoint.new_partof(obj), group_id, pos_in_grp + 1 ]
            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)
        elif option == 16: #auto route single
            self.auto_route_obj(obj)
        elif option == 17: #auto route group
            if isinstance(obj, ObjectContainer) and obj.assoc is Camera:
                for camera in self.level_file.cameras:
                    self.auto_route_obj(camera)
            elif isinstance(obj, MapObjects):
                self.leveldatatreeview.objects.bound_to = self.level_file.objects
                for object in self.level_file.objects.objects:
                    self.auto_route_obj(object)
        elif option == 19: #snap to route single
            if obj.has_route() and obj.route != -1 and obj.route < len(self.level_file.routes):
                pointone_pos = self.level_file.routes[obj.route].points[0].position
                obj.position = Vector3( pointone_pos.x+ 250,pointone_pos.y, pointone_pos.z + 250 )
                
                self.level_view.do_redraw()
        elif option == 20: #snap to route all cameras
            for camera in self.level_file.cameras:
                if camera.has_route() and camera.route != -1 and camera.route < len(self.level_file.routes):
                    route_points = self.level_file.cameraroutes[camera.route].points
                    if len(route_points) > 0:
                        pointone_pos = route_points[0].position
                        camera.position = Vector3( pointone_pos.x + 250,pointone_pos.y, pointone_pos.z + 250  )
                        if len( route_points ) > 1:
                            pointtwo_pos = route_points[1].position
                        
                    
                            angle = atan2(pointtwo_pos.x - pointone_pos.x, pointtwo_pos.z - pointone_pos.z) * (180.0/3.14159);
                            camera.rotation = Rotation.from_euler( Vector3(0, angle + 90, 0)  ) 

            self.level_view.do_redraw()         
        elif option == 21: #key checkpoints
            self.level_file.checkpoints.set_key_cps()
            self.level_view.do_redraw()
        elif option == 22: #respawns
            self.level_file.create_respawns()
            self.level_view.do_redraw()
        elif option == 22.5: #reassign respawns
            self.level_file.reassign_respawns()
            self.level_view.do_redraw()
        elif option == 23:
            self.level_file.remove_unused_routes()
            self.level_view.do_redraw()
        elif option == 24:
            self.level_file.copy_enemy_to_item()
        elif option == 25:
            self.level_file.remove_unused_cameras()
            self.level_view.do_redraw()
         
        self.leveldatatreeview.set_objects(self.level_file)   

    @catch_exception
    def button_add_advanced(self, option, obj = None):
        pass

    @catch_exception
    def button_add_from_addi_options_multi(self, option, objs = None): 
        if option == -1 or option == -1.5:
            sum_x = 0
            count_x = 0
            for object in objs:
            
                if hasattr(object, "position"):
                    if option == -1:
                
                        sum_x += object.position.x
                    else:
                        sum_x += object.position.z
                    count_x += 1
            mean_x = sum_x / count_x
            
            for object in objs:
            
                if hasattr(object, "position"):
                    if option == -1:
                        object.position.x = mean_x
                    else:
                        object.position.z = mean_x
            self.level_view.do_redraw()
    
        if option == 0:
            added_item_boxes = []
            diff_vector = objs[1].position - objs[0].position
            diff_angle = Vector3( *objs[1].rotation.get_euler()) - Vector3( *objs[0].rotation.get_euler())
            
            for i in range(1, 4):
                default_item_box = libkmp.MapObject.default_item_box()
                default_item_box.position = objs[0].position + diff_vector * ( i / 4.0)
                default_item_box.rotation = Rotation.from_euler(Vector3( *objs[0].rotation.get_euler()) + diff_angle * ( i / 4.0) )
            
                self.level_file.objects.objects.append(default_item_box)
                added_item_boxes.append(default_item_box)
        
        
            self.level_view.do_redraw()
            return added_item_boxes
        if option == 0.5:
            to_ground = self.button_add_from_addi_options_multi(0, objs)
            for obj in to_ground:
                self.action_ground_spec_object(obj)
            return
        if option == 1: #currently unused
            for obj in objs:
                if isinstance(obj, MapObject) and obj.route_info is not None:
                    pass
        if option == 2:
            max_group = 0
            #iterate through all checkpoints to find the "new" group
            for checkgroup in self.level_file.checkpoints.groups:
                for checkpoint in checkgroup.points:
                    max_group = max(max_group, checkpoint.unk1)
            for obj in objs:
                obj.unk1 = max_group + 1

    def auto_route_obj(self, obj):
        #do object route
        route_collec = self.level_file.routes if isinstance(obj, MapObject) else self.level_file.cameraroutes
        if isinstance(obj, MapObject):
            route_data = load_route_info(get_kmp_name(obj.objectid))
            #print("route_data",  route_data )
        elif isinstance(obj, Camera):
            is_object = False
            if obj.type == 1 or (obj.type in [2, 5, 6] and  obj.name == "mkwi"):
                route_data = 2
            else:
                route_data = -1
            
        if route_data == 2:
        
            if obj.route == -1:
                self.add_points_around_obj(obj,route_data,True)
            elif  obj.route > len(route_collec) - 1 :
                self.add_points_around_obj(obj,route_data,True)
            elif  len(route_collec[obj.route].points) < 2:
                self.add_points_around_obj(obj,2 - len(route_collec[obj.route].points),False)
                
                
        elif route_data == 3:
            if obj.route == -1:
                self.add_points_around_obj(obj,5,True)
        

    def add_points_around_obj(self, obj, num = 2, create = False):
        if num == 0:
            return
            
        route_collec = self.level_file.routes if isinstance(obj, MapObject) else self.level_file.cameraroutes

        if create:
            if isinstance(obj, MapObject):
                new_route_group = libkmp.Route.new()
               
            elif isinstance(obj, Camera):
                new_route_group = libkmp.Route.new_camera()
            route_collec.append(new_route_group)
            obj.route = len(route_collec) - 1 


        if create:
            route_collec[obj.route].used_by.append(obj)
        #create new points around the object
        self.place_points(obj, num)
        
        
    def place_points(self, obj, num):   
        new_point = libkmp.RoutePoint.new()
        
        new_point.partof = self.level_file.routes[obj.route] if isinstance(obj, MapObject) else self.level_file.cameraroutes[obj.route] 
        self.object_to_be_added = [new_point, obj.route, -1]
    
        
        left_vector = obj.rotation.get_vectors()[2]
        
        first_point = [obj.position.x - 500 * left_vector.x, obj.position.z - 500 * left_vector.z] 
        self.action_add_object(*first_point)
        
        if num > 1:
            second_point = [obj.position.x + 500 * left_vector.x, obj.position.z + 500 * left_vector.z]      
            self.action_add_object(*second_point)

    @catch_exception
    def action_add_object(self, x, z):
    
        if self.object_to_be_added is None and self.objects_to_be_added is not None:
            self.action_add_objects(x, z)
        else: 
            y = 0
            object, group, position = self.object_to_be_added
            #if self.editorconfig.getboolean("GroundObjectsWhenAdding") is True:
            if isinstance(object, libkmp.Checkpoint):
                y = object.start.y
            else:
                if self.level_view.collision is not None:
                    y_collided = self.level_view.collision.collide_ray_downwards(x, z)
                    if y_collided is not None:
                        y = y_collided

            self.action_add_object_3d(x, y, z)

    @catch_exception
    def action_add_object_3d(self, x, y, z):
        object, group, position = self.object_to_be_added
        if position is not None and position < 0:
            position = 99999999 # this forces insertion at the end of the list

        if isinstance(object, libkmp.Checkpoint):
            if len(self.last_position_clicked) == 1:
                try:
                    placeobject = deepcopy(object)
                except:
                    placeobject = object.copy()

                x1, y1, z1 = self.last_position_clicked[0]
                placeobject.start.x = x1
                placeobject.start.y = y1
                placeobject.start.z = z1

                placeobject.end.x = x
                placeobject.end.y = y
                placeobject.end.z = z
                self.last_position_clicked = []
                # For convenience, create a group if none exists yet.
                if group == 0 and not self.level_file.checkpoints.groups:
                    self.level_file.checkpoints.groups.append(libkmp.CheckpointGroup.new())


                self.level_file.checkpoints.groups[group].points.insert(position + self.points_added, placeobject)
                self.points_added += 1
                self.level_view.do_redraw()
                self.set_has_unsaved_changes(True)
                self.leveldatatreeview.set_objects(self.level_file)

                self.select_tree_item_bound_to(placeobject)
            else:
                self.last_position_clicked = [(x, y, z)]

        else:
            try:
                placeobject = deepcopy(object)
            except:
                placeobject = object.copy()
            placeobject.position.x = x
            placeobject.position.y = y
            placeobject.position.z = z


            if isinstance(object, libkmp.EnemyPoint):
                # For convenience, create a group if none exists yet.
                if group == 0 and not self.level_file.enemypointgroups.groups:
                    self.level_file.enemypointgroups.groups.append(libkmp.EnemyPointGroup.new())
                self.level_file.enemypointgroups.groups[group].points.insert(position + self.points_added, placeobject)
                self.points_added += 1
            elif isinstance(object, libkmp.ItemPoint):
                self.level_file.itempointgroups.groups[group].points.insert(position + self.points_added, placeobject)
                self.points_added += 1
            elif isinstance(object, libkmp.RoutePoint):
                # For convenience, create a group if none exists yet.
                if group == 0 and not self.level_file.routes:
                    self.level_file.routes.append(libkmp.Route.new())
                if object.partof.type == 0:
                    placeobject.partof = self.level_file.routes[group]
                    self.level_file.routes[group].points.insert(position+ self.points_added, placeobject)
                elif object.partof.type == 1:
                    placeobject.partof = self.level_file.cameraroutes[group]
                    self.level_file.cameraroutes[group].points.insert(position+ self.points_added, placeobject)
                self.points_added += 1
            elif isinstance(object, libkmp.MapObject):
                self.level_file.objects.objects.append(placeobject)
                placeobject.set_route_info()
                if placeobject.route != -1:
                    self.level_file.routes[placeobject.route].used_by.append(placeobject) 
                    if placeobject.route_info == 3:
                        pass
                        
                
                if placeobject.route_info == 3:
                    route_points = self.level_file.routes[placeobject.route].points
                    closest_idx = -1
                    closest_dis = 99999999999999
                    for i, point in enumerate( route_points ):
                        
                        distance = (placeobject.position - point.position).norm()
                        if distance < closest_dis:
                            closest_idx = i
                            closest_dis = distance
                    object.unk_2a = closest_idx    
                
            elif isinstance(object, libkmp.KartStartPoint):
                self.level_file.kartpoints.positions.append(placeobject)
            elif isinstance(object, libkmp.JugemPoint):
                self.level_file.respawnpoints.append(placeobject)
                #find the closest enemy point
                
               
            elif isinstance(object, libkmp.Area):
                self.level_file.areas.areas.append(placeobject)
            elif isinstance(object, libkmp.Camera):
                self.level_file.cameras.append(placeobject)
            else:
                raise RuntimeError("Unknown object type {0}".format(type(object)))

            self.level_view.do_redraw()
            self.leveldatatreeview.set_objects(self.level_file)
            self.set_has_unsaved_changes(True)

            self.select_tree_item_bound_to(placeobject)

    @catch_exception
    def action_add_objects(self, x, z):
        y = 0
        if self.level_view.collision is not None:
            y_collided = self.level_view.collision.collide_ray_downwards(x, z)
            if y_collided is not None:
                y = y_collided

        self.action_add_objects_3d(x, y, z)
    
    @catch_exception
    def action_add_objects_3d(self, x, y, z):
    
        #areas should be grounded and place at the position
        #cameras should be +3000 on x, +3000 on y
        #routes should be +3500 on x, +3000 on y 
    
        #place all down as normal, and then do adjustments

        
        placed_objects = []
        
        added_area = False
        
        for object, group, position in self.objects_to_be_added:

            if position is not None and position < 0:
                position = 99999999 # this forces insertion at the end of the list

            if isinstance(object, libkmp.Checkpoint):
                if len(self.last_position_clicked) == 1:
                    placeobject = deepcopy(object)

                    x1, y1, z1 = self.last_position_clicked[0]
                    placeobject.start = Vector3(x1, y1, z1)
                    placeobject.end = Vector3(x, y, z)

                    self.last_position_clicked = []
                    self.level_file.checkpoints.groups[group].points.insert(position + self.points_added, placeobject)
                    self.points_added += 1
                    self.level_view.do_redraw()
                    self.set_has_unsaved_changes(True)
                    self.leveldatatreeview.set_objects(self.level_file)
                else:
                    self.last_position_clicked = [(x, y, z)]

            else:
                placeobject = deepcopy(object)
                placed_objects.append(placeobject)
                
                if hasattr(placeobject, "position"):
                    placeobject.position = Vector3(x, y, z)

                if isinstance(object, libkmp.EnemyPoint):
                    self.level_file.enemypointgroups.groups[group].points.insert(position + self.points_added, placeobject)
                    self.points_added += 1
                if isinstance(object, libkmp.ItemPoint):
                    self.level_file.itempointgroups.groups[group].points.insert(position + self.points_added, placeobject)
                    self.points_added += 1
                
                elif isinstance(object, libkmp.RoutePoint):
                    self.level_file.routes[group].points.insert(position, placeobject)
                elif isinstance(object, libkmp.MapObject):
        
                
                    self.level_file.objects.objects.append(placeobject)
                elif isinstance(object, libkmp.KartStartPoint):
                    self.level_file.kartpoints.positions.append(placeobject)
                elif isinstance(object, libkmp.JugemPoint):
                    self.level_file.respawnpoints.append(placeobject)
                elif isinstance(object, libkmp.Area):
                    added_area = True
                    self.level_file.areas.areas.append(placeobject)
                elif isinstance(object, libkmp.Camera):
                    self.level_file.cameras.append(placeobject)
                elif isinstance(object, Route):
                    if object.type == 0:
                        self.level_file.routes.append(placeobject)
                    elif object.type == 1:
                        self.level_file.cameraroutes.append(placeobject)
                else:
                    raise RuntimeError("Unknown object type {0}".format(type(object)))

        for object in placed_objects:
            if isinstance(object, libkmp.Camera):
            
                if added_area: 
                    object.position.x += 3000
                object.position.y += 3000
                

                if object.type in [2, 5, 6]:
                    object.route = len(self.level_file.cameraroutes) - 1
                    self.level_file.cameraroutes[object.route].used_by.append(object)              
                    
                    self.level_file.cameraroutes[object.route].points[0].position = Vector3( object.position.x, object.position.y, object.position.z + 3500)      
                    self.level_file.cameraroutes[object.route].points[1].position = Vector3( object.position.x, object.position.y, object.position.z - 3500)           
                
            if isinstance(object, libkmp.Area):
                if object.type == 0:
                    object.camera_index = len(self.level_file.cameras) - 1
                    self.level_file.cameras[-1].used_by.append(object)
                elif object.type == 9:
                    object.position.z += 300
            if isinstance(object, Route): 
                
                for point in object.points:
                    self.action_ground_spec_object(point)
            if isinstance(object, libkmp.MapObject):
            
                object.route = len(self.level_file.routes) - 1    
            

                      
                self.level_file.routes[object.route].used_by.append(object) 
            
                for point in self.level_file.routes[object.route].points:
                    point.position = point.position + object.position
                    self.action_ground_spec_object(point)
                

                
                
        self.pik_control.update_info()
        self.level_view.do_redraw()
        self.leveldatatreeview.set_objects(self.level_file)
        self.set_has_unsaved_changes(True)

    

    @catch_exception
    def action_move_objects(self, deltax, deltay, deltaz):
        for i in range(len(self.level_view.selected_positions)):
            for j in range(len(self.level_view.selected_positions)):
                pos = self.level_view.selected_positions
                if i != j and pos[i] == pos[j]:
                    print("What the fuck")
        for pos in self.level_view.selected_positions:
            """obj.x += deltax
            obj.z += deltaz
            obj.x = round(obj.x, 6)
            obj.z = round(obj.z, 6)
            obj.position_x = obj.x
            obj.position_z = obj.z
            obj.offset_x = 0
            obj.offset_z = 0

            if self.editorconfig.getboolean("GroundObjectsWhenMoving") is True:
                if self.pikmin_gen_view.collision is not None:
                    y = self.pikmin_gen_view.collision.collide_ray_downwards(obj.x, obj.z)
                    obj.y = obj.position_y = round(y, 6)
                    obj.offset_y = 0"""
            pos.x += deltax
            pos.y += deltay
            pos.z += deltaz

            self.level_view.gizmo.move_to_average(self.level_view.selected_positions)


        #if len(self.pikmin_gen_view.selected) == 1:
        #    obj = self.pikmin_gen_view.selected[0]
        #    self.pik_control.set_info(obj, obj.position, obj.rotation)

        #self.pikmin_gen_view.update()
        self.level_view.do_redraw()
        self.pik_control.update_info()
        self.set_has_unsaved_changes(True)


    @catch_exception
    def action_change_object_heights(self, deltay):
        for obj in self.pikmin_gen_view.selected:
            obj.y += deltay
            obj.y = round(obj.y, 6)
            obj.position_y = obj.y
            obj.offset_y = 0

        if len(self.pikmin_gen_view.selected) == 1:
            obj = self.pikmin_gen_view.selected[0]
            self.pik_control.set_info(obj, (obj.x, obj.y, obj.z), obj.get_rotation())

        #self.pikmin_gen_view.update()
        self.pikmin_gen_view.do_redraw()
        self.set_has_unsaved_changes(True)

    def keyPressEvent(self, event: QtGui.QKeyEvent):

        if event.key() == Qt.Key_Escape:
            self.points_added = 0
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_NONE)
            self.pik_control.button_add_object.setChecked(False)
            #self.pik_control.button_move_object.setChecked(False)

        if event.key() == Qt.Key_Shift:
            self.level_view.shift_is_pressed = True
        elif event.key() == Qt.Key_R:
            self.level_view.rotation_is_pressed = True
        elif event.key() == Qt.Key_H:
            self.level_view.change_height_is_pressed = True

        if event.key() == Qt.Key_W:
            self.level_view.MOVE_FORWARD = 1
        elif event.key() == Qt.Key_S:
            self.level_view.MOVE_BACKWARD = 1
        elif event.key() == Qt.Key_A:
            self.level_view.MOVE_LEFT = 1
        elif event.key() == Qt.Key_D:
            self.level_view.MOVE_RIGHT = 1
        elif event.key() == Qt.Key_Q:
            self.level_view.MOVE_UP = 1
        elif event.key() == Qt.Key_E:
            self.level_view.MOVE_DOWN = 1

        if event.key() == Qt.Key_Plus:
            self.level_view.zoom_in()
        elif event.key() == Qt.Key_Minus:
            self.level_view.zoom_out()

        if event.key() == Qt.Key_C:
            if len(self.level_view.selected) == 1:
                if isinstance( self.level_view.selected[0], (KMPPoint) ):
                    self.connect_start = self.level_view.selected[0]
                    self.level_view.connecting_mode = True

    def keyReleaseEvent(self, event: QtGui.QKeyEvent):
        if event.key() == Qt.Key_Shift:
            self.level_view.shift_is_pressed = False
        elif event.key() == Qt.Key_R:
            self.level_view.rotation_is_pressed = False
        elif event.key() == Qt.Key_H:
            self.level_view.change_height_is_pressed = False

        if event.key() == Qt.Key_W:
            self.level_view.MOVE_FORWARD = 0
        elif event.key() == Qt.Key_S:
            self.level_view.MOVE_BACKWARD = 0
        elif event.key() == Qt.Key_A:
            self.level_view.MOVE_LEFT = 0
        elif event.key() == Qt.Key_D:
            self.level_view.MOVE_RIGHT = 0
        elif event.key() == Qt.Key_Q:
            self.level_view.MOVE_UP = 0
        elif event.key() == Qt.Key_E:
            self.level_view.MOVE_DOWN = 0

        if event.key() == Qt.Key_C:
            self.level_view.connecting_mode = False
            self.connect_start = None

    def reset_move_flags(self):
        self.level_view.MOVE_FORWARD = 0
        self.level_view.MOVE_BACKWARD = 0
        self.level_view.MOVE_LEFT = 0
        self.level_view.MOVE_RIGHT = 0
        self.level_view.MOVE_UP = 0
        self.level_view.MOVE_DOWN = 0
        self.level_view.shift_is_pressed = False
        self.level_view.rotation_is_pressed = False
        self.level_view.change_height_is_pressed = False

    def action_rotate_object(self, deltarotation):
        #obj.set_rotation((None, round(angle, 6), None))
        #print(deltarotation)
        for rot in self.level_view.selected_rotations:
            if deltarotation.x != 0:
                rot.rotate_around_x(deltarotation.x) #originally y
            elif deltarotation.y != 0:
                rot.rotate_around_y(deltarotation.y) #originally z
            elif deltarotation.z != 0:
                rot.rotate_around_z(deltarotation.z) #originally x

        if self.rotation_mode.isChecked():
            middle = self.level_view.gizmo.position

            for position in self.level_view.selected_positions:
                diff = position - middle
                diff.y = 0.0

                length = diff.norm()
                if length > 0:
                    diff.normalize()
                    angle = atan2(diff.x, diff.z)
                    angle += deltarotation.y
                    position.x = middle.x + length * sin(angle)
                    position.z = middle.z + length * cos(angle)

        """
        if len(self.pikmin_gen_view.selected) == 1:
            obj = self.pikmin_gen_view.selected[0]
            self.pik_control.set_info(obj, obj.position, obj.rotation)
        """
        #self.pikmin_gen_view.update()
        self.level_view.do_redraw()
        self.set_has_unsaved_changes(True)
        self.pik_control.update_info()

    def action_ground_objects(self):
        for pos in self.level_view.selected_positions:
            if self.level_view.collision is None:
                return None
            height = self.level_view.collision.collide_ray_closest(pos.x, pos.z, pos.y)

            if height is not None:
                pos.y = height

        self.pik_control.update_info()
        self.level_view.gizmo.move_to_average(self.level_view.selected_positions)
        self.set_has_unsaved_changes(True)
        self.level_view.do_redraw()

    def action_ground_spec_object(self, obj):
    
        if self.level_view.collision is None:
            return None
        pos = obj.position
        height = self.level_view.collision.collide_ray_closest(pos.x, pos.z, pos.y)

        if height is not None:
            pos.y = height

    def action_delete_objects(self):
        #tobedeleted = []
        for obj in self.level_view.selected:
            if isinstance(obj, libkmp.EnemyPoint):
                for group in self.level_file.enemypointgroups.groups:
                    if obj in group.points:
                        group.points.remove(obj)
                        break

            if isinstance(obj, libkmp.ItemPoint):
                for group in self.level_file.itempointgroups.groups:
                    if obj in group.points:
                        group.points.remove(obj)
                        break


            elif isinstance(obj, libkmp.RoutePoint):
                for route in self.level_file.routes:
                    if obj in route.points:
                        route.points.remove(obj)
                        break

            elif isinstance(obj, libkmp.Checkpoint):
                for group in self.level_file.checkpoints.groups:
                    if obj in group.points:
                        group.points.remove(obj)
                        break

            elif isinstance(obj, libkmp.MapObject):
                if obj.route != -1 and obj.route < len(self.level_file.routes):
                    self.level_file.routes[obj.route].used_by.remove(obj)
                   
                self.level_file.objects.objects.remove(obj)
            elif isinstance(obj, libkmp.KartStartPoint):
                self.level_file.kartpoints.positions.remove(obj)
            elif isinstance(obj, libkmp.JugemPoint):
                self.level_file.remove_respawn(obj)
                #self.level_file.respawnpoints.remove(obj)
            elif isinstance(obj, libkmp.Area):
                if obj.camera_index != -1 and obj.camera_index < len(self.level_file.areas.areas):
                    self.level_file.cameras[obj.camera_index].used_by.remove(obj)
                
            
                self.level_file.areas.areas.remove(obj)
            elif isinstance(obj, libkmp.Camera):
                if obj.route != -1 and obj.route < len(self.level_file.routes):
                    self.level_file.routes[obj.route].used_by.remove(obj)
            
                self.level_file.cameras.remove(obj)
            elif isinstance(obj, libkmp.CheckpointGroup):
                #self.level_file.checkpoints.groups.remove(obj)
                self.level_file.remove_group(obj)
            elif isinstance(obj, (libkmp.EnemyPointGroup, libkmp.ItemPointGroup) ):
                #self.level_file.enemypointgroups.groups.remove(obj)

                self.level_file.remove_group(obj)
            
            elif isinstance(obj, libkmp.Route):
                #set all 
                route_index = 0
                for i, route in enumerate(self.level_file.routes):
                    if obj == route:
                        route_index = i
                        break
                for object in obj.used_by:
                    object.route = -1    
                self.level_file.routes.remove(obj)
            
                self.level_file.reset_routes( route_index )
       
        self.level_view.selected = []
        self.level_view.selected_positions = []
        self.level_view.selected_rotations = []

        self.pik_control.reset_info()
        self.leveldatatreeview.set_objects(self.level_file)
        self.level_view.gizmo.hidden = True
        #self.pikmin_gen_view.update()
        self.level_view.do_redraw()
        self.set_has_unsaved_changes(True)

    def update_route_used_by(self, obj, old, new):
        #print("update route used by", obj, old, new)
        if old == new:
            return
        
        #print("old", self.level_file.routes[old].used_by, "new", self.level_file.routes[new].used_by)
        
        if old != -1:
            self.level_file.routes[old].used_by.remove(obj)
        if new != -1:
            self.level_file.routes[new].used_by.append(obj)
        
        #print("old", self.level_file.routes[old].used_by, "new", self.level_file.routes[new].used_by)
        
    def update_camera_used_by(self, obj, old, new):
        #print("update route used by", obj, old, new)
        if old == new:
            return
        
        #print("old", self.level_file.routes[old].used_by, "new", self.level_file.routes[new].used_by)
        
        if old != -1:
            self.level_file.cameras[old].used_by.remove(obj)
        if new != -1:
            self.level_file.cameras[new].used_by.append(obj)
        
    def on_cut_action_triggered(self):
        self.on_copy_action_triggered()
        self.action_delete_objects()

    def on_copy_action_triggered(self):
        # Widgets are unpickleable, so they need to be temporarily stashed. This needs to be done
        # recursively, as top-level groups main contain points associated with widgets too.
        object_to_widget = {}
        object_to_usedby = {}
        object_to_partof = {}
        pending = list(self.level_view.selected)
        while pending:
            obj = pending.pop(0)
            if hasattr(obj, 'widget'):
                object_to_widget[obj] = obj.widget
                obj.widget = None
            if hasattr(obj, 'used_by'):
                object_to_usedby[obj] = obj.used_by
                obj.used_by = None
            if hasattr(obj, 'partof'):
                object_to_partof[obj] = obj.partof
                obj.partof = None
            if hasattr(obj, '__dict__'):
                pending.extend(list(obj.__dict__.values()))
            if isinstance(obj, list):
                pending.extend(obj)
        try:
            # Effectively serialize the data.
            data = pickle.dumps(self.level_view.selected)
        finally:
            # Restore the widgets and usedby.
            for obj, widget in object_to_widget.items():
                obj.widget = widget
            for obj, widget in object_to_usedby.items():
                obj.used_by = widget
            for obj, partof in object_to_partof.items():
                obj.partof = partof
        mimedata = QtCore.QMimeData()
        mimedata.setData("application/mkwii-track-editor", QtCore.QByteArray(data))
        QtWidgets.QApplication.instance().clipboard().setMimeData(mimedata)

    def on_paste_action_triggered(self):
        mimedata = QtWidgets.QApplication.instance().clipboard().mimeData()
        data = bytes(mimedata.data("application/mkwii-track-editor"))
        if not data:
            return

        copied_objects = pickle.loads(data)
        if not copied_objects:
            return

        # If an tree item is selected, use it as a reference point for adding the objects that are
        # about to be pasted.
        selected_items = self.leveldatatreeview.selectedItems()
        selected_obj = selected_items[-1].bound_to if selected_items else None

        target_path = None
        target_checkpoint_group = None
        target_route = None

        if isinstance(selected_obj, KMPPoint):
            to_deal_with = self.level_file.get_to_deal_with(selected_obj)
            groupind, target_path, pointind = to_deal_with.find_group_of_point(selected_obj)
            for group in to_deal_with.groups:
                if selected_obj in group.points:
                    break
        elif isinstance(selected_obj, PointGroup):
            target_path = selected_obj

        if isinstance(selected_obj, libkmp.Route):
            target_route = selected_obj
        elif isinstance(selected_obj, libkmp.RoutePoint):
            for route in self.level_file.routes:
                if selected_obj in route.points:
                    target_route = route
                    break
            for route in self.level_file.cameraroutes:
                if selected_obj in route.points:
                    target_route = route
                    break

        added = []

        for obj in copied_objects:
            # Group objects.
            if isinstance(obj, PointGroup):
                self.duplicate_group(obj)
                #to_deal_with = self.level_file.get_to_deal_with(obj)
                #obj.id = self.level_file.enemypointgroups.new_group_id()
                #self.level_file.enemypointgroups.groups.append(obj)

            elif isinstance(obj, libkmp.Route):
                obj.used_by = []
                if obj.type == 0:
                    self.level_file.routes.append(obj)
                else:
                    self.level_file.cameraroutes.append(obj)
                for point in obj.points:
                    point.partof = obj

            # Objects in group objects.
            elif isinstance(obj, libkmp.KMPPoint):
                to_deal_with = self.level_file.get_to_deal_with(obj)
                if target_path is None:
                    if not self.level_file.enemypointgroups.groups:
                        self.level_file.enemypointgroups.groups.append(libkmp.EnemyPointGroup.new())
                    target_path = self.level_file.enemypointgroups.groups[-1]

              
                target_path.points.append(obj)

            elif isinstance(obj, libkmp.RoutePoint):
                if target_route is None:
                    if not self.level_file.routes:
                        self.level_file.routes.append(libkmp.Route.new())
                    target_route = self.level_file.routes[-1]
                
                if target_route is not None:
                    obj.partof = target_route
                target_route.points.append(obj)

            # Autonomous objects.
            elif isinstance(obj, libkmp.MapObject):
                self.level_file.objects.objects.append(obj)
            elif isinstance(obj, libkmp.KartStartPoint):
                self.level_file.kartpoints.positions.append(obj)
            elif isinstance(obj, libkmp.JugemPoint):
                
                self.level_file.respawnpoints.append(obj)
            elif isinstance(obj, libkmp.Area):
                self.level_file.areas.areas.append(obj)
            elif isinstance(obj, libkmp.Camera):
                obj.used_by = []
                self.level_file.cameras.append(obj)
            elif isinstance(obj, libkmp.CannonPoint):
                max_cannon_id = -1
                for point in self.level_file.cannonpoints:
                    max_cannon_id = max(point.id, max_cannon_id)
                obj.id = max_cannon_id + 1
                self.level_file.cannonpoints.append(obj)
            elif isinstance(obj, libkmp.MissionPoint):
                self.level_file.missionpoints.append(obj)
            else:
                continue

            added.append(obj)

        if not added:
            return

        self.set_has_unsaved_changes(True)
        self.leveldatatreeview.set_objects(self.level_file)

        self.select_tree_item_bound_to(added[-1])
        self.level_view.selected = added
        self.level_view.selected_positions = []
        self.level_view.selected_rotations = []
        for obj in added:
            if hasattr(obj, 'position'):
                self.level_view.selected_positions.append(obj.position)
            if hasattr(obj, 'start') and hasattr(obj, 'end'):
                self.level_view.selected_positions.append(obj.start)
                self.level_view.selected_positions.append(obj.end)
            if hasattr(obj, 'rotation'):
                self.level_view.selected_rotations.append(obj.rotation)

        self.update_3d()

    def update_3d(self):
        self.level_view.gizmo.move_to_average(self.level_view.selected_positions)
        self.level_view.do_redraw()

    def select_from_3d_to_treeview(self):
        if self.level_file is not None:
            selected = self.level_view.selected
            if len(selected) == 1:
                currentobj = selected[0]
                item = None
                if isinstance(currentobj, libkmp.EnemyPoint):
                    for i in range(self.leveldatatreeview.enemyroutes.childCount()):
                        child = self.leveldatatreeview.enemyroutes.child(i)
                        item = get_treeitem(child, currentobj)
                        if item is not None:
                            break

                if isinstance(currentobj, libkmp.ItemPoint):
                    for i in range(self.leveldatatreeview.itemroutes.childCount()):
                        child = self.leveldatatreeview.itemroutes.child(i)
                        item = get_treeitem(child, currentobj)
                        if item is not None:
                            break

                elif isinstance(currentobj, libkmp.Checkpoint):
                    for i in range(self.leveldatatreeview.checkpointgroups.childCount()):
                        child = self.leveldatatreeview.checkpointgroups.child(i)
                        item = get_treeitem(child, currentobj)
                        if item is not None:
                            break

                elif isinstance(currentobj, libkmp.RoutePoint):
                    to_look_through = self.leveldatatreeview.objectroutes if currentobj.partof.type == 0 else self.leveldatatreeview.cameraroutes


                    for i in range(to_look_through.childCount()):
                        child = to_look_through.child(i)
                        item = get_treeitem(child, currentobj)
                        if item is not None:
                            break

                elif isinstance(currentobj, libkmp.MapObject):
                    item = get_treeitem(self.leveldatatreeview.objects, currentobj)
                elif isinstance(currentobj, libkmp.Camera):
                    item = get_treeitem(self.leveldatatreeview.cameras, currentobj)
                elif isinstance(currentobj, libkmp.Area):
                    item = get_treeitem(self.leveldatatreeview.areas, currentobj)
                elif isinstance(currentobj, libkmp.JugemPoint):
                    item = get_treeitem(self.leveldatatreeview.respawnpoints, currentobj)
                elif isinstance(currentobj, libkmp.KartStartPoint):
                    item = get_treeitem(self.leveldatatreeview.kartpoints, currentobj)

                #assert item is not None
                if item is not None:
                    #self._dontselectfromtree = True
                    self.leveldatatreeview.setCurrentItem(item)

    @catch_exception
    def action_update_info(self):   

        if self.level_file is not None:
            selected = self.level_view.selected
            if len(selected) == 1:
                
                currentobj = selected[0]
                
                
                if isinstance(currentobj, Route):
                    objects = []
                    for thing in currentobj.used_by:
                        if isinstance(thing, MapObject):
                            objects.append(get_kmp_name(thing.objectid))
                        elif isinstance(thing, Camera):
                            for i, camera in enumerate(self.level_file.cameras):
                                if camera is thing:
                                    objects.append("Camera {0}".format(i))

                    
                    self.pik_control.set_info(currentobj, self.update_3d, objects)
                else:
                    self.pik_control.set_info(currentobj, self.update_3d)
                
                
                self.pik_control.update_info()
                
                
                
            else:            
                #need a way to add a control for cameras being selected
                if self.leveldatatreeview.cameras.isSelected():
                    self.pik_control.set_info(self.leveldatatreeview.cameras.bound_to, self.update_3d)
                    self.pik_control.update_info()
                    
                else:
                    self.pik_control.reset_info("{0} objects selected".format(len(self.level_view.selected)))
                    self.pik_control.set_objectlist(selected)

                # Without emitting any signal, programmatically update the currently selected item
                # in the tree view.
                with QtCore.QSignalBlocker(self.leveldatatreeview):
                    if selected:
                        # When there is more than one object selected, pick the last one.
                        self.select_tree_item_bound_to(selected[-1])
                    else:
                        # If no selection occurred, ensure that no tree item remains selected. This
                        # is relevant to ensure that non-pickable objects (such as the top-level
                        # items) do not remain selected when the user clicks on an empty space in
                        # the viewport.
                        for selected_item in self.leveldatatreeview.selectedItems():
                            selected_item.setSelected(False)

    @catch_exception
    def mapview_showcontextmenu(self, position):
        self.reset_move_flags()
        context_menu = QMenu(self)
        action = QAction("Copy Coordinates", self)
        action.triggered.connect(self.action_copy_coords_to_clipboard)
        context_menu.addAction(action)
        context_menu.exec(self.sender().mapToGlobal(position))
        context_menu.destroy()

    def action_copy_coords_to_clipboard(self):
        if self.current_coordinates is not None:
            QApplication.clipboard().setText(", ".join(str(x) for x in self.current_coordinates))

    def action_update_position(self, event, pos):
        self.current_coordinates = pos
        
        selected = self.level_view.selected
        


        if len(selected) == 1 and hasattr( selected[0], "position") :
            obj_pos = selected[0].position
            
            
            if self.level_view.collision is not None:
                height = self.level_view.collision.collide_ray_closest(obj_pos.x, obj_pos.z, obj_pos.y)
                if height is not None:
                    y_ground = height
            
                    y_diff = obj_pos.y - y_ground
                    
                    if y_diff >= 0:
                        above_formatted = ", object at y = %f, above by %f units"%(obj_pos.y , round(y_diff) )
                    
                        self.statusbar.showMessage(str(pos) + above_formatted )
                    else:
                        below_formatted = ", object at y = %f, below by %f units"%(obj_pos.y , round(y_diff) )
                    
                        self.statusbar.showMessage(str(pos) + below_formatted )
                    return
        

        self.statusbar.showMessage(str(pos))

        
    def action_connectedto_end(self):
        
        if self.connect_start is not None and self.level_view.connecting_mode:
            self.ready_to_connect = True
        else:
            self.ready_to_connect = False

                 

    def action_connectedto_final(self):
        if not self.ready_to_connect:
            return
        self.ready_to_connect = False

        #create a new group
        if len(self.level_view.selected) == 0:
            to_deal_with = self.level_file.get_to_deal_with(self.connect_start)
            
            obj = self.connect_start
            start_groupind, start_group, start_pointind = to_deal_with.find_group_of_point(self.connect_start)
            if start_group.num_next() == 6:
                return

            
            point_to_add = to_deal_with.get_new_point()
            group_to_add = to_deal_with.get_new_group()
            if start_pointind == len(start_group.points) - 1:
                group_to_add.id = to_deal_with.new_group_id()
                to_deal_with.groups.append(group_to_add)
                self.object_to_be_added = [point_to_add, group_to_add.id, 0 ]
            else:
                self.split_group( start_group, self.connect_start )

                group_to_add.id = to_deal_with.new_group_id()
                to_deal_with.groups.append(group_to_add)

                group_to_add.add_new_prev(start_groupind)
                start_group.add_new_next(group_to_add.id)

                self.object_to_be_added = [point_to_add, group_to_add.id, 0 ]

            start_group.remove_next(start_group.id)
            start_group.remove_prev(start_group.id)

            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)


        elif len(self.level_view.selected) != 1:
            return
        else:
            endpoint = self.level_view.selected[0]

            if isinstance(endpoint, EnemyPoint) and isinstance(self.connect_start, EnemyPoint):
                to_deal_with = self.level_file.enemypointgroups
            elif isinstance(endpoint, ItemPoint) and isinstance(self.connect_start, ItemPoint):
                to_deal_with = self.level_file.itempointgroups
            elif isinstance(endpoint, Checkpoint) and isinstance(self.connect_start, Checkpoint):
                to_deal_with = self.level_file.checkpoints
            if to_deal_with is not None:
                self.connect_two_groups(endpoint, to_deal_with)
                return
            

        self.connect_start = None
        

        self.leveldatatreeview.set_objects(self.level_file)
        self.update_3d()
        self.set_has_unsaved_changes(True)   

    def connect_two_groups(self, endpoint, to_deal_with):
        if endpoint == self.connect_start:
            return

        end_groupind, end_group, end_pointind = to_deal_with.find_group_of_point(endpoint)
        
        start_groupind, start_group, start_pointind = to_deal_with.find_group_of_point(self.connect_start)

        #make sure that start_group is good to add another
        if start_group.num_next() == 6:
            return

        #if drawing from and endpoint to a startpoint of the next group
        if (start_pointind + 1 == len(start_group.points) and end_pointind == 0):
            if end_group.num_prev() < 6:
                start_group.add_new_next( end_groupind  )
                end_group.add_new_prev(start_groupind)

                start_group.remove_next(start_group.id)
                start_group.remove_prev(start_group.id)
            
            return

        self.split_group( start_group, self.connect_start )
        group_1 = to_deal_with.groups[-1]
        self.split_group( end_group, end_group.points[end_pointind - 1])
        group_2 = to_deal_with.groups[-1]

        #redo connections
        print(start_group.id)
        start_group.remove_next(start_group.id)
        start_group.remove_prev(start_group.id)

        start_group.add_new_next(group_2.id)
        #group_1.add_new_next(group_2.id)
        group_2.add_new_prev(start_groupind)


    def set_and_start_copying(self):
        #print(self.level_view.selected)
        #print(isinstance( self.level_view.selected[0], (MapObject, Area, Camera)))
        if len(self.level_view.selected) == 1 and isinstance( self.level_view.selected[0], (MapObject, Area, Camera)):
            self.obj_to_copy = self.level_view.selected[0]
            self.copy_current_obj()



    def copy_current_obj(self):
        if self.obj_to_copy is not None:
            self.object_to_be_added = None
            #if isinstance(self.obj_to_copy, libkmp.MapObject) and self.obj_to_copy.route_info == 2: 
            if isinstance(self.obj_to_copy, (libkmp.MapObject, Camera) ) and self.obj_to_copy.route_info is not None : 
                
                self.objects_to_be_added = []
                
                new_route = libkmp.Route()    
                
                if self.obj_to_copy.route != -1 :
                    for point in self.level_file.routes[self.obj_to_copy.route].points: 
                        new_point = libkmp.RoutePoint.new()
                        new_point.partof = new_route
                        new_point.position = point.position - self.obj_to_copy.position
                        new_route.points.append(new_point)
                else:
                    for i in range(2):
                        point = libkmp.RoutePoint.new()
                        new_point.partof = new_route
                        new_route.points.append(point)
                
                self.objects_to_be_added.append( [new_route, None, None ]  )
                

                new_object = self.obj_to_copy.copy()
                self.objects_to_be_added.append( [new_object, None, None ]  )

            else:
                self.object_to_be_added = [self.obj_to_copy, None, None ]
            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)
        #will use self.obj_to_copy


    def auto_qol(self):
        self.level_file.auto_qol_all()
        self.leveldatatreeview.set_objects(self.level_file)    
        self.leveldatatreeview.bound_to_group(self.level_file)
        self.level_view.do_redraw()
        
        self.update_3d()

def find_file(rarc_folder, ending):
    for filename in rarc_folder.files.keys():
        if filename.endswith(ending):
            return filename
    raise RuntimeError("No Course File found!")


def get_file_safe(rarc_folder, ending):
    for filename in rarc_folder.files.keys():
        if filename.endswith(ending):
            return rarc_folder.files[filename]
    return None


import sys
def except_hook(cls, exception, traceback):
    sys.__excepthook__(cls, exception, traceback)

POTENTIALLY_EDITING_EVENTS = (
    QtCore.QEvent.KeyRelease,
    QtCore.QEvent.MouseButtonRelease,
)


class Application(QtWidgets.QApplication):

    document_potentially_changed = QtCore.pyqtSignal()

    def notify(self, receiver: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if event.type() in POTENTIALLY_EDITING_EVENTS:
            if isinstance(receiver, QtGui.QWindow):
                QtCore.QTimer.singleShot(0, self.document_potentially_changed)

        return super().notify(receiver, event)




if __name__ == "__main__":
    #import sys
    import platform
    import signal
    import argparse
    from PyQt5.QtCore import QLocale

    QLocale.setDefault(QLocale(QLocale.English))

    sys.excepthook = except_hook

    parser = argparse.ArgumentParser()
    parser.add_argument("--load", default=None,
                        help="Path to the ARC or BOL file to be loaded.")
    parser.add_argument("--additional", default=None, choices=['model', 'collision'],
                        help="Whether to also load the additional BMD file (3D model) or BCO file "
                        "(collision file).")

    args = parser.parse_args()

    app = Application(sys.argv)

    signal.signal(signal.SIGINT, lambda _signal, _frame: app.quit())
    """
    app.setStyle(QtWidgets.QStyleFactory.create("Fusion"))

    
    role_colors = []
    role_colors.append((QtGui.QPalette.Window, QtGui.QColor(60, 60, 60)))
    role_colors.append((QtGui.QPalette.WindowText, QtGui.QColor(200, 200, 200)))
    role_colors.append((QtGui.QPalette.Base, QtGui.QColor(25, 25, 25)))
    role_colors.append((QtGui.QPalette.AlternateBase, QtGui.QColor(60, 60, 60)))
    role_colors.append((QtGui.QPalette.ToolTipBase, Qt.black))
    role_colors.append((QtGui.QPalette.ToolTipText, QtGui.QColor(200, 200, 200)))
    try:
        role_colors.append((QtGui.QPalette.PlaceholderText, QtGui.QColor(160, 160, 160)))
    except AttributeError:
        pass
    role_colors.append((QtGui.QPalette.Text, QtGui.QColor(200, 200, 200)))
    role_colors.append((QtGui.QPalette.Button, QtGui.QColor(55, 55, 55)))
    role_colors.append((QtGui.QPalette.ButtonText, QtGui.QColor(200, 200, 200)))
    role_colors.append((QtGui.QPalette.BrightText, Qt.red))
    role_colors.append((QtGui.QPalette.Light, QtGui.QColor(65, 65, 65)))
    role_colors.append((QtGui.QPalette.Midlight, QtGui.QColor(60, 60, 60)))
    role_colors.append((QtGui.QPalette.Dark, QtGui.QColor(45, 45, 45)))
    role_colors.append((QtGui.QPalette.Mid, QtGui.QColor(50, 50, 50)))
    role_colors.append((QtGui.QPalette.Shadow, Qt.black))
    role_colors.append((QtGui.QPalette.Highlight, QtGui.QColor(45, 140, 225)))
    role_colors.append((QtGui.QPalette.HighlightedText, Qt.black))
    role_colors.append((QtGui.QPalette.Link, QtGui.QColor(40, 130, 220)))
    role_colors.append((QtGui.QPalette.LinkVisited, QtGui.QColor(110, 70, 150)))
    palette = QtGui.QPalette()
    for role, color in role_colors:
        palette.setColor(QtGui.QPalette.Disabled, role, QtGui.QColor(color).darker())
        palette.setColor(QtGui.QPalette.Active, role, color)
        palette.setColor(QtGui.QPalette.Inactive, role, color)
    app.setPalette(palette)
    """
    if platform.system() == "Windows":
        import ctypes
        myappid = 'P2GeneratorsEditor'  # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    os.makedirs("lib/temp", exist_ok=True)

    with open("log.txt", "w") as f:
        #sys.stdout = f
        #sys.stderr = f
        print("Python version: ", sys.version)
        editor_gui = GenEditor()
        editor_gui.setWindowIcon(QtGui.QIcon('resources/icon.ico'))

        app.document_potentially_changed.connect(
            editor_gui.on_document_potentially_changed)


        editor_gui.show()

        if args.load is not None:
            def load():
                editor_gui.load_file(args.load, additional=args.additional)

            QtCore.QTimer.singleShot(0, load)

        err_code = app.exec()

    sys.exit(err_code)