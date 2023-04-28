from argparse import _MutuallyExclusiveGroup
import contextlib
import pickle
import traceback
import os
from timeit import default_timer
from copy import deepcopy
from io import TextIOWrapper, BytesIO, StringIO
from math import sin, cos, atan2
import json
from PIL import Image
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

from lib import bti
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
from widgets.editor_widgets import ErrorAnalyzer, ErrorAnalyzerButton, LoadingFix
from widgets.file_select import FileSelect
from widgets.data_editor_options import routed_cameras
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
        self.undo_history_disabled_count: int  = 0

        try:
            self.configuration = read_config()
            print("Config file loaded")
        except FileNotFoundError as e:
            print("No config file found, creating default config...")
            self.configuration = make_default_config()

        self.pathsconfig = self.configuration["default paths"]
        self.editorconfig = self.configuration["editor"]
        self.current_gen_path = None
        self.setAcceptDrops(True)
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

        self.bco_coll = None
        self.loaded_archive = None
        self.loaded_archive_file = None
        self.last_position_clicked = []

        self.connect_start = None
        self.select_start = None
        self.ready_to_connect = False

        self._dontselectfromtree = False

        #self.dolphin = Game()
        #self.level_view.dolphin = self.dolphin
        self.last_chosen_type = ""

        self.first_time_3dview = True

        self.restore_geometry()

        self.undo_history.append(self.generate_undo_entry())

        self.obj_to_copy = None
        self.objs_to_copy = None
        self.points_added = 0

        with open ("toadette.qss") as f:
            lines = f.read()
            lines = lines.strip()
            self.setStyleSheet(lines)
        self.leveldatatreeview.set_objects(self.level_file)
        self.leveldatatreeview.bound_to_group(self.level_file)

        if self.editorconfig.get("default_view") == "3dview":
            self.change_to_3dview(True)

        self.undo_history.append(self.generate_undo_entry())

    def save_geometry(self):
        if "geometry" not in self.configuration:
            self.configuration["geometry"] = {}
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

        if "window_geometry" in geo_config:
            self.restoreGeometry(to_byte_array(geo_config["window_geometry"]))
        if "window_state" in geo_config:
            self.restoreState(to_byte_array(geo_config["window_state"]))
        if "window_splitter" in geo_config:
            self.horizontalLayout.restoreState(to_byte_array(geo_config["window_splitter"]))

    def closeEvent(self, event: QtGui.QCloseEvent):
        self.save_geometry()

        if self._user_made_change:
            msgbox = QtWidgets.QMessageBox(self)
            size = self.fontMetrics().height() * 3
            msgbox.setIconPixmap(QtGui.QIcon('resources/warning.svg').pixmap(size, size))
            msgbox.setWindowTitle("Unsaved Changes")
            msgbox.setText('Are you sure you want to exit the application?')
            msgbox.addButton('Cancel', QtWidgets.QMessageBox.RejectRole)
            exit_button = msgbox.addButton('Exit', QtWidgets.QMessageBox.DestructiveRole)
            msgbox.exec_()
            if msgbox.clickedButton() != exit_button:
                event.ignore()
                return

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
        enemy_paths = self.level_file.enemypointgroups
        enemy_path_data = tuple((not path.points, enemy_paths.get_idx(path)) for path in enemy_paths.groups)

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
            self.error_analyzer_button.analyze_kmp(self.level_file)

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
        # Early out if undo history is temporarily disabled.
        if self.undo_history_disabled_count:
            return

        undo_entry = self.generate_undo_entry()

        if self.undo_history[-1] != undo_entry:
            bol_changed = self.undo_history[-1].bol_hash != undo_entry.bol_hash

            self.undo_history.append(undo_entry)
            self.redo_history.clear()
            self.update_undo_redo_actions()

            if bol_changed:
                if update_unsaved_changes:
                    self.set_has_unsaved_changes(True)

                self.error_analyzer_button.analyze_kmp(self.level_file)

    def update_undo_redo_actions(self):
        self.undo_action.setEnabled(len(self.undo_history) > 1)
        self.redo_action.setEnabled(bool(self.redo_history))

    @contextlib.contextmanager
    def undo_history_disabled(self):
        self.undo_history_disabled_count += 1
        try:
            yield
        finally:
            self.undo_history_disabled_count -= 1

        self.on_document_potentially_changed()

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

        if self.visibility_menu.enemyroutes.is_visible():
            for enemy_path in self.level_file.enemypointgroups.groups:
                for enemy_path_point in enemy_path.points:
                    extend(enemy_path_point.position)
        if self.visibility_menu.itemroutes.is_visible():
            for item_path in self.level_file.itempointgroups.groups:
                for item_path_point in item_path.points:
                    extend(item_path_point.position)
        if self.visibility_menu.objects.is_visible():
            for object_route in self.level_file.routes:
                for object_route_point in object_route.points:
                    extend(object_route_point.position)
        if self.visibility_menu.cameras.is_visible():
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
            for area in self.level_file.areas:
                extend(area.position)
        if self.visibility_menu.replaycameras.is_visible():
            for area in self.level_file.replayareas:
                extend(area.position)
        if self.visibility_menu.cameras.is_visible():
            for camera in self.level_file.cameras:
                extend(camera.position)
        if self.visibility_menu.checkpoints.is_visible():
            for respawn_point in self.level_file.respawnpoints:
                extend(respawn_point.position)
        if self.visibility_menu.kartstartpoints.is_visible():
            for karts_point in self.level_file.kartpoints.positions:
                extend(karts_point.position)

        if self.visibility_menu.cannonpoints.is_visible():
            for karts_point in self.level_file.cannonpoints:
                extend(karts_point.position)

        if self.visibility_menu.missionsuccesspoints.is_visible():
            for karts_point in self.level_file.missionpoints:
                extend(karts_point.position)

        """
        if self.level_view.collision is not None and self.level_view.collision.verts:
            vertices = self.level_view.collision.verts
            min_x = min(x for x, _y, _z in vertices)
            min_y = min(y for _x, y, _z in vertices)
            min_z = min(z for _x, _y, z in vertices)
            max_y = max(y for _x, y, _z in vertices)
            max_x = max(x for x, _y, _z in vertices)
            max_z = max(z for _x, _y, z in vertices)

            if extent:
                extent[0] = min(extent[0], min_x)
                extent[1] = min(extent[1], min_y)
                extent[2] = min(extent[2], min_z)
                extent[3] = max(extent[3], max_y)
                extent[4] = max(extent[4], max_x)
                extent[5] = max(extent[5], max_z)
            else:
                extend.extend([min_x, min_y, min_z, max_y, max_x, max_z])
        """
        return tuple(extent) or (0, 0, 0, 0, 0, 0)

    def tree_select_arrowkey(self):
        current = self.leveldatatreeview.selectedItems()
        if len(current) == 1:
            self.tree_select_object(current[0])

    def tree_select_object(self, item):
        #print("Selected mkdd_editor:", item)
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

        if hasattr(item, "bound_to"):
            self.pik_control.set_buttons(item.bound_to)

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
        self.leveldatatreeview = LevelDataTreeView(self.centralwidget, self.visibility_menu)
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

        self.file_load_action.triggered.connect(self.button_load_level)
        self.save_file_action.triggered.connect(self.button_save_level)
        self.save_file_as_action.triggered.connect(self.button_save_level_as)

        self.file_menu.addAction(self.file_load_action)
        self.file_menu.addMenu(self.file_load_recent_menu)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.save_file_action)
        self.file_menu.addAction(self.save_file_as_action)

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

        self.edit_menu.addSeparator()

        self.rotation_mode = QAction("Rotate Positions around Pivot", self)
        self.rotation_mode.setCheckable(True)
        self.rotation_mode.setChecked(True)
        self.edit_menu.addAction(self.rotation_mode)

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
        self.choose_bco_area.setShortcut("Ctrl+K")

        # Misc
        self.misc_menu = QMenu(self.menubar)
        self.misc_menu.setTitle("Misc")

        self.frame_action = QAction("Frame Selection/All", self)
        self.frame_action.triggered.connect(
            lambda _checked: self.frame_selection(adjust_zoom=True))
        self.frame_action.setShortcut("F")

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

        self.choose_default_view = QMenu("Choose Default View")
        self.load_as_topdown = self.choose_default_view.addAction("Topdown View")
        self.load_as_topdown.setCheckable(True)
        self.load_as_topdown.setChecked( self.editorconfig.get("default_view") == "topdownview" )
        self.load_as_topdown.triggered.connect( lambda: self.on_default_view_changed("topdownview") )
        self.load_as_3dview = self.choose_default_view.addAction("3D View")
        self.load_as_3dview.setCheckable(True)
        self.load_as_3dview.setChecked( self.editorconfig.get("default_view") == "3dview" )
        self.load_as_3dview.triggered.connect( lambda: self.on_default_view_changed("3dview") )
        if self.editorconfig.get("default_view") not in ("topdownview", "3dview"):
            self.on_default_view_changed("topdownview")
        self.misc_menu.addMenu(self.choose_default_view)
        self.misc_menu.addSeparator()

        self.do_generation = QAction("Run Generation")
        self.do_generation.triggered.connect(self.auto_generation)
        self.misc_menu.addAction(self.do_generation)
        self.do_generation.setShortcut("Ctrl+3")

        self.do_cleanup = QAction("Run Cleanup")
        self.do_cleanup.triggered.connect(self.auto_cleanup)
        self.misc_menu.addAction(self.do_cleanup)
        self.do_cleanup.setShortcut("Ctrl+4")

        self.misc_menu.addAction(self.frame_action)
        self.analyze_action = QAction("Analyze for common mistakes", self)
        self.analyze_action.triggered.connect(self.analyze_for_mistakes)
        self.misc_menu.addAction(self.analyze_action)

        self.menubar.addAction(self.file_menu.menuAction())
        self.menubar.addAction(self.edit_menu.menuAction())
        #self.menubar.addAction(self.visibility_menu.menuAction())
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

            if self.level_view.collision is not None:
                self.level_view.collision.hidden_coltypes = self.configuration["editor"]["hidden_collision_types"]
                self.level_view.collision.hidden_colgroups = self.configuration["editor"]["hidden_collision_type_groups"]

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

    def on_visible_menu_changed(self, element, index):
        if hasattr(self.visibility_menu, element):
            toggle = getattr(self.visibility_menu, element)
            if index == 0:
                toggle.change_view_status()
            elif index == 1:
                toggle.change_select_status()
            self.on_filter_update()

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

    def on_default_geometry_changed(self, default_filetype):
        self.editorconfig["addi_file_on_load"] = default_filetype
        save_cfg(self.configuration)

        collision_actions = [self.auto_load_bco, self.auto_load_bmd, self.auto_load_none, self.auto_load_choose]
        collision_options = ("BCO", "BMD", "None", "Choose")

        for i, option in enumerate(collision_options):
            collision_actions[i].setChecked(option == default_filetype)

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

    def on_default_view_changed(self, view_string):
        self.editorconfig["default_view"] = view_string
        save_cfg(self.configuration)

        view_actions = [self.load_as_topdown, self.load_as_3dview]
        view_options = ("topdownview", "3dview")

        for i, option in enumerate(view_options):
            view_actions[i].setChecked(option == view_string)

    def on_default_view_changed(self, view_string):
        self.editorconfig["default_view"] = view_string
        save_cfg(self.configuration)

        view_actions = [self.load_as_topdown, self.load_as_3dview]
        view_options = ("topdownview", "3dview")

        for i, option in enumerate(view_options):
            view_actions[i].setChecked(option == view_string)

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

        self.pik_control.button_stop_object.pressed.connect(self.button_stop_adding)
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
        self.leveldatatreeview.split.connect(self.split_group_from_tree)
        self.leveldatatreeview.remove_type.connect(self.remove_all_of_type)
        self.leveldatatreeview.select_type.connect(self.select_all_of_type)
        self.leveldatatreeview.remove_all.connect(self.remove_all_points)
        self.leveldatatreeview.visible_changed.connect(lambda element, index: self.on_visible_menu_changed(element, index))



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
        to_deal_with.reset_ids()

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
        self.set_has_unsaved_changes(True)

    def select_all_of_group(self, item):
        if hasattr(item, "bound_to"):
            group = item.bound_to
        else:
            to_deal_with = self.level_file.get_to_deal_with(item)
            group_idx, group, point_idx = to_deal_with.find_group_of_point(item)
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
        self.action_update_info()

    def delete_all_of_group(self, item):
        to_deal_with = self.level_file.get_to_deal_with(item)
        group_idx, group, point_idx = to_deal_with.find_group_of_point(item)
        for point in reversed(group.points):
            to_deal_with.remove_point(point)
        self.update_3d()
        self.action_update_info()
        self.leveldatatreeview.set_objects(self.level_file)
        self.set_has_unsaved_changes(True)

    def remove_all_of_type(self, item):
        obj = item.bound_to
        to_delete = []
        if isinstance(obj, MapObject):
            to_delete = [mapobject for mapobject in self.level_file.objects.objects if mapobject.objectid == obj.objectid]
            for obj in to_delete:
                self.level_file.objects.objects.remove(obj)
        elif isinstance(obj, Area):
            to_delete = [area for area in self.level_file.areas if area.type == obj.type]
            for obj in to_delete:
                self.level_file.areas.remove(obj)
        self.update_3d()
        self.pik_control.update_info()
        self.leveldatatreeview.set_objects(self.level_file)
        self.set_has_unsaved_changes(True)

    def select_all_of_type(self, item):
        if hasattr(item, "bound_to"):
            obj = item.bound_to
        else:
            obj = item
        if isinstance(obj, MapObject):
            to_select = [mapobject for mapobject in self.level_file.objects.objects if mapobject.objectid == obj.objectid]
        elif isinstance(obj, Area):
            to_select = [area for area in self.level_file.areas if area.type == obj.type]
        self.level_view.selected = to_select
        self.level_view.selected_positions = [mapobject.position for mapobject in to_select]
        self.level_view.selected_rotations = [mapobject.rotation for mapobject in to_select]

        self.update_3d()
        self.pik_control.reset_info()

    def remove_all_points(self, pointgroups : PointGroups):
        pointgroups.remove_all()
        self.pik_control.update_info()
        self.level_view.do_redraw()
        self.leveldatatreeview.set_objects(self.level_file)
        self.set_has_unsaved_changes(True)

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
    def button_load_level(self, checked=False, filepath=None, add_to_ini=True ):
        _ = checked

        if filepath is None:
            filepath, chosentype = QFileDialog.getOpenFileName(
                self, "Open File",
                self.pathsconfig["kmp"],
                "KMP(*.kmp);;KMP files (*.kmp);;All files (*)",
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
                    error_string = kmp_file.fix_file() #will do a popup for 'stuff fixed at load'

                    if len(error_string) > 0:
                        initial_errors = LoadingFix(self.level_file, parent=self)
                        initial_errors.set_text(error_string)
                        initial_errors.exec_()
                        initial_errors.deleteLater()

                    self.setup_kmp_file(kmp_file, filepath, add_to_ini)
                    self.leveldatatreeview.set_objects(kmp_file)
                    self.leveldatatreeview.bound_to_group(kmp_file)
                    self.current_gen_path = filepath

                    filepath_base = os.path.dirname(filepath)

                    collisionfile = filepath_base+"/course.kcl"
                    if os.path.exists(collisionfile):
                        self.load_collision_kcl(collisionfile)

                    self.frame_selection(adjust_zoom=True)

                except Exception as error:
                    print("Error appeared while loading:", error)
                    traceback.print_exc()
                    open_error_dialog(str(error), self)

            self.update_3d()


    def load_optional_bmd(self, bmdfile):
        alternative_mesh = load_textured_bmd(bmdfile)
        with open("lib/temp/temp.obj", "r") as f:
            verts, faces, normals = py_obj.read_obj(f)

        self.setup_collision(verts, faces, bmdfile, alternative_mesh)

    def load_optional_bco(self, collisionfile):
        bco_coll = RacetrackCollision()
        verts = []
        faces = []

        with open(collisionfile, "rb") as f:
            bco_coll.load_file(f)
        self.bco_coll = bco_coll

        for vert in bco_coll.vertices:
            verts.append(vert)

        for v1, v2, v3, collision_type, rest in bco_coll.triangles:
            faces.append(((v1 + 1, None), (v2 + 1, None), (v3 + 1, None), collision_type))
        model = CollisionModel(bco_coll)
        self.setup_collision(verts, faces, collisionfile, alternative_mesh=model)

    def setup_kmp_file(self, bol_file, filepath, add_to_ini):
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
        if add_to_ini:
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
            "KMP(*.kmp);;All files (*)",
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
        self.bco_coll = None
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

        self.level_view.collision.hidden_coltypes = \
            set(int(t) for t in editor_config.get("hidden_collision_types", "").split(",") if t)
        self.level_view.collision.hidden_colgroups = \
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
            if hasattr(self.leveldatatreeview.currentItem(), 'bound_to'):
                obj = self.leveldatatreeview.currentItem().bound_to

        if obj is not None:
            add_something = True
            #add points to group at current position
            if isinstance(obj, KMPPoint):
                self.button_add_from_addi_options( 11, obj)
            elif isinstance(obj, PointGroups):
                self.button_add_from_addi_options( 0, obj )
            elif isinstance(obj, ObjectContainer) and obj.assoc == ObjectRoute:
                self.button_add_from_addi_options( 5 )
                self.button_add_from_addi_options( 6, self.level_file.routes[-1] )
            elif isinstance(obj, ObjectContainer) and obj.assoc == CameraRoute:
                self.button_add_from_addi_options( 5.5 )
                self.button_add_from_addi_options( 6, self.level_file.cameraroutes[-1] )
            elif isinstance(obj, RoutePoint):
                self.button_add_from_addi_options( 15, obj)
            elif isinstance(obj, ObjectContainer) and obj.assoc == JugemPoint:
                self.button_add_from_addi_options( 9, True)
            elif isinstance(obj, MapObject) and obj.has_route():
                self.button_add_from_addi_options( 6, obj)
            else:
                print('nothing caught')
                add_something = False

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
                self.object_to_be_added = None
                self.pik_control.button_add_object.setChecked(False)
                self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_NONE)
                self.leveldatatreeview.set_objects(self.level_file)

                self.select_tree_item_bound_to(obj)

            elif self.object_to_be_added is not None:
                self.pik_control.button_add_object.setChecked(True)
                self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)

                #self.pikmin_gen_view.setContextMenuPolicy(Qt.DefaultContextMenu)

    @catch_exception
    def button_stop_adding(self):
        self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_NONE)
        self.pik_control.button_add_object.setChecked(False)
        # see if you are adding a camera point
        if self.object_to_be_added is not None:
            thing_added = self.object_to_be_added[0]
            if isinstance( thing_added, RoutePoint ) and isinstance( thing_added.partof, CameraRoute):
                group : Route =  self.level_file.cameraroutes[ self.object_to_be_added[1] ]
                #if you created a new route from scratch
                if self.points_added == len(group.points) and self.points_added > 0:
                    for point in group.points[:-1]:
                        point.unk1 = 50

        self.points_added = 0
        self.objects_to_be_added = None
        self.object_to_be_added = None

    #this is the function that the new side buttons calls
    @catch_exception
    def button_add_from_addi_options(self, option, obj = None):
        self.points_added = 0
        self.pik_control.button_add_object.setChecked(False)
        self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_NONE)
        self.objects_to_be_added = None
        self.object_to_be_added = None

        if option == "add_enemygroup": #add an empty enemy group
            to_deal_with = self.level_file.get_to_deal_with(obj)
            if len(to_deal_with.groups) != 1 or len(to_deal_with.groups[0].points) != 0:
                to_deal_with.add_new_group()
            self.button_add_from_addi_options(1, to_deal_with.groups[-1])

        elif option == 1: #adding an enemy point to a group, the group is obj
            to_deal_with = self.level_file.get_to_deal_with(obj)
            thing_to_add = to_deal_with.get_new_point()
            self.object_to_be_added = [thing_to_add, obj, -1 ]

            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)
        elif option =="assign_jgpt_ckpt": #regarding assigning checkpoints to routes
            if isinstance(obj, Checkpoint):
                obj.assign_to_closest(self.level_file.respawnpoints)
            elif isinstance(obj, JugemPoint):
                self.level_file.reassign_one_respawn(obj)
            else:
                self.level_file.reassign_respawns()
                self.level_view.do_redraw()
        elif option == "add_object": #add item box
            #self.addobjectwindow_last_selected_category = 6

            default_item_box = libkmp.MapObject.new(obj)
            self.object_to_be_added = [default_item_box, None, None ]

            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)
        elif option == "generic_copy":   #generic copy
            #self.addobjectwindow_last_selected_category = 6
            self.objects_to_be_added = []
            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)

            self.obj_to_copy = obj
            self.copy_current_obj(False)
        elif option == "generic_copy_routed":  #copy with new route

            self.objects_to_be_added = []
            self.object_to_be_added = None

            new_route = self.level_file.get_route_for_obj(obj)
            if obj.route_obj is not None :
                for point in obj.route_obj.points:
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
                new_camera = libkmp.OpeningCamera.default()
                self.objects_to_be_added.append( [new_camera, None, None ]  )

            elif isinstance(obj, libkmp.MapObject):
                new_object = obj.copy()
                self.objects_to_be_added.append( [new_object, None, None ]  )

            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)

            self.object_to_be_added = None
        elif option == 5: #new object route
            new_route_group = libkmp.ObjectRoute()
            self.level_file.routes.append(new_route_group)
        elif option == 5.5: #new camera route
            new_route_group = libkmp.CameraRoute.new()
            self.level_file.cameraroutes.append(new_route_group)
        elif option == "add_routepoints_end": #add route point to end of route
            if obj.route_obj is None:
                route_collec = self.level_file.get_route_container(obj)
                new_route = self.level_file.get_route_for_obj(obj)
                obj.route_obj = new_route
                new_route.used_by = [obj]
                route_collec.append(new_route)

            new_point = libkmp.RoutePoint.new()
            new_point.partof = obj
            self.object_to_be_added = [new_point, obj.route_obj, -1 ]

            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)
        elif option == "add_area_gener": #add new area
            #self.addobjectwindow_last_selected_category = 7
            self.object_to_be_added = [libkmp.Area.default(obj), None, None ]
            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)
        elif option == "add_area_objs": #add new type 8/9 areas
            self.objects_to_be_added = []
            self.objects_to_be_added.append( [libkmp.Area.default(8), None, None ]  )
            self.objects_to_be_added.append( [libkmp.Area.default(9), None, None ]  )
            self.object_to_be_added = None
            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)
        elif option == "add_camera":  #add new camera with route

            if obj == 0:
                self.level_file.cameras.add_goal_camera()
                self.leveldatatreeview.set_objects(self.level_file)
                self.update_3d()
                return

            if obj in routed_cameras:
                self.objects_to_be_added = []
                self.object_to_be_added = None

                new_route = libkmp.CameraRoute.new()

                for i in range(2):
                    point = libkmp.RoutePoint.new()
                    point.partof = new_route
                    if i == 0:
                        point.unk1 = 50
                    new_route.points.append(point)

                #self.addobjectwindow_last_selected_category = 8
                self.objects_to_be_added.append( [new_route, None, None ]  )
                self.objects_to_be_added.append( [libkmp.OpeningCamera.default(obj), None, None ] )
            else:
                self.objects_to_be_added = None
                self.object_to_be_added = [libkmp.OpeningCamera.default(obj), None, None ]

            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)
        elif option == "add_jgpt": #add new respawn point
            rsp = libkmp.JugemPoint.new()
            self.object_to_be_added = [rsp, obj, None ]
            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)
        elif option == "merge_groups": #merge enemy/item/route
            obj.merge_groups()
        elif option == "new_enemy_points": #new enemy point here
            #find its position in the enemy point group
            to_deal_with = self.level_file.get_to_deal_with(obj)
            if to_deal_with.num_total_points() == 255:
                self.button_stop_adding()
                return
            start_groupind, start_group, start_pointind = to_deal_with.find_group_of_point(obj)

            thing_to_add = to_deal_with.get_new_point()
            self.object_to_be_added = [thing_to_add, start_groupind, start_pointind + 1  ]
            #self.object_to_be_added[0].group = obj.id
            #actively adding objects
            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)
        elif option == "add_rarea_rout": #area camera route add
            self.objects_to_be_added = []
            new_area = libkmp.Area.default()
            new_camera = libkmp.ReplayCamera.default(2)
            new_route = libkmp.CameraRoute.new()

            for i in range(2):
                point = libkmp.RoutePoint.new()
                point.partof = new_route
                new_route.points.append(point)
            new_route.points[0].unk1 = 30

            self.objects_to_be_added.append( [new_route, None, None ]  )
            self.objects_to_be_added.append( [new_camera, None, None ]  )
            self.objects_to_be_added.append( [new_area, None, None ]  )


            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)

            self.object_to_be_added = None
        elif option == "add_rarea_stat": #area camera add
            self.objects_to_be_added = []
            new_area = libkmp.Area.default()
            new_camera = libkmp.ReplayCamera.default(1)

            self.objects_to_be_added.append( [new_camera, None, None ]  )
            self.objects_to_be_added.append( [new_area, None, None ]  )

            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)

            self.object_to_be_added = None
        elif option == "copy_area_camera":
            self.object_to_be_added = [obj, None, None ]
            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)
            self.objects_to_be_added = None
        elif option == "add_routepoints": #add new route point here - 15
            group_id = -1
            pos_in_grp = -1
            idx = 0


            route_container = self.level_file.get_route_container(obj.partof)

            for group_idx, group in enumerate(route_container):
                for point_idx, point in enumerate(group.points):
                    if point is obj:
                        group_id = group_idx
                        pos_in_grp = point_idx
                        break


            self.object_to_be_added = [libkmp.RoutePoint.new_partof(obj), group_id, pos_in_grp + 1 ]
            self.pik_control.button_add_object.setChecked(True)
            self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)
        elif option == "auto_route_single": #auto route single
            self.auto_route_obj(obj)
        elif option == "auto_route": #auto route group
            if isinstance(obj, ObjectContainer) and obj.assoc is Camera:
                for camera in self.level_file.cameras:
                    self.auto_route_obj(camera)
            elif isinstance(obj, MapObjects):
                self.leveldatatreeview.objects.bound_to = self.level_file.objects
                for object in self.level_file.objects.objects:
                    self.auto_route_obj(object)
        elif option == "auto_keycheckpoints": #key checkpoints
            self.level_file.checkpoints.set_key_cps()
            self.level_view.do_redraw()
        elif option == "autocreate_jgpt": #respawns
            self.level_file.create_respawns()
            self.level_view.do_redraw()
        elif option == 22.5: #reassign respawns
            self.level_file.reassign_respawns()
            self.level_view.do_redraw()
        elif option == "remove_unused": #remove unused object routes
            self.level_file.remove_unused_object_routes()
            self.level_view.do_redraw()
        elif option == 23.5: #remove unused camera routes
            self.level_file.remove_unused_camera_routes()
            self.level_view.do_redraw()
        elif option == "copy_enemy_item": #copy enemy to item
            self.level_file.copy_enemy_to_item()
        elif option == "remove_unused_cams": #remove unused cameras
            self.level_file.remove_unused_cameras()
            self.level_view.do_redraw()
        elif option == "removed_unused_jgpt": #remove unused respawns:
            self.level_file.remove_unused_respawns()
        elif option == 27:
            obj.find_closest_enemypoint()
        self.leveldatatreeview.set_objects(self.level_file)

    @catch_exception
    def button_add_from_addi_options_multi(self, option, objs = None):
        if option == "align_x" or option == "align_z":
            sum_x = 0
            count_x = 0
            for object in objs:

                if hasattr(object, "position"):
                    if option == "align_x":

                        sum_x += object.position.x
                    else:
                        sum_x += object.position.z
                    count_x += 1
            mean_x = sum_x / count_x

            for object in objs:

                if hasattr(object, "position"):
                    if option == "align_x":
                        object.position.x = mean_x
                    else:
                        object.position.z = mean_x

        elif option == "add_items_between":
            added_item_boxes = []
            diff_vector = objs[1].position - objs[0].position
            diff_angle = Vector3( *objs[1].rotation.get_euler()) - Vector3( *objs[0].rotation.get_euler())

            for i in range(1, 4):
                default_item_box = libkmp.MapObject.default_item_box()
                default_item_box.position = objs[0].position + diff_vector * ( i / 4.0)
                default_item_box.rotation = Rotation.from_euler(Vector3( *objs[0].rotation.get_euler()) + diff_angle * ( i / 4.0) )

                self.level_file.objects.objects.append(default_item_box)
                added_item_boxes.append(default_item_box)

            self.leveldatatreeview.set_objects(self.level_file)
            return added_item_boxes
        elif option == "add_items_between_ground":
            to_ground = self.button_add_from_addi_options_multi(0, objs)
            for obj in to_ground:
                self.action_ground_spec_object(obj)
            return
        elif option == 1: #currently unused
            for obj in objs:
                if isinstance(obj, MapObject) and obj.route_info is not None:
                    pass
        elif option == "dec_enemy_scale": #decrease scale
            for obj in objs:
                obj.scale = max(0, obj.scale - 5)
        elif option == "inc_enemy_scale": #increase scale
            for obj in objs:
                obj.scale += 5

        self.update_3d()
        self.set_has_unsaved_changes(True)

    def auto_route_obj(self, obj):
        #do object route
        route_collec = self.level_file.get_route_container(obj)
        if isinstance(obj, MapObject):
            route_data = load_route_info(get_kmp_name(obj.objectid))
        elif isinstance(obj, Camera):
            if obj.has_route() :
                route_data = 2
            else:
                route_data = -1
        elif isinstance(obj, Area):
            if obj.type == 3:
                route_data = 2
            else:
                route_data = -1

        if route_data == 2:
            if obj.route_obj is None:
                self.add_points_around_obj(obj,route_data,True)
            elif  len(obj.route_obj.points) < 2:
                self.add_points_around_obj(obj,2 - len(obj.route_obj.points),False)
        elif route_data == 3:
            if obj.route_obj is None:
                self.add_points_around_obj(obj,5,True)

    def add_points_around_obj(self, obj, num = 2, create = False):
        if num == 0:
            return

        route_collec = self.level_file.get_route_container(obj)
        set_speed = False
        if create:
            if isinstance(obj, (MapObject, Area) ):
                new_route_group = libkmp.ObjectRoute.new()

            elif isinstance(obj, Camera):
                set_speed = True
                new_route_group = libkmp.CameraRoute.new()
            obj.route_obj = new_route_group
            route_collec.append(new_route_group)

        if create:
            obj.route_obj.used_by.append(obj)
        #create new points around the object
        self.place_points(obj, num, set_speed)

    def place_points(self, obj, num, set_speed = False):
        new_point = libkmp.RoutePoint.new()
        if set_speed:
            new_point.unk1 = 50
        self.object_to_be_added = [new_point, obj.route_obj, -1]

        left_vector = obj.rotation.get_vectors()[2]

        first_point = [obj.position.x - 500 * left_vector.x, obj.position.z - 500 * left_vector.z]
        self.action_add_object(*first_point)

        new_point = libkmp.RoutePoint.new()
        self.object_to_be_added = [new_point, obj.route_obj, -1]

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

                to_deal_with = self.level_file.get_to_deal_with(object)
                if to_deal_with.num_total_points() == 255:
                    self.button_stop_adding()
            else:
                self.last_position_clicked = [(x, y, z)]

        else:
            try:
                placeobject = object.copy()
            except:
                placeobject = deepcopy(object)
            placeobject.position.x = x
            placeobject.position.y = y
            placeobject.position.z = z


            if isinstance(object, (libkmp.EnemyPoint, ItemPoint) ):
                # For convenience, create a group if none exists yet.
                to_deal_with = self.level_file.get_to_deal_with(object)
                if group == 0 and not to_deal_with.groups:
                    to_deal_with.groups.append(to_deal_with.get_new_group())
                if isinstance(group, PointGroup):
                    group.points.insert(position + self.points_added, placeobject)
                else:
                    to_deal_with.groups[group].points.insert(position + self.points_added, placeobject)
                self.points_added += 1
                if to_deal_with.num_total_points() == 255:
                    self.button_stop_adding()
            elif isinstance(object, libkmp.RoutePoint):
                route_container = self.level_file.get_route_container(object.partof)
                if isinstance(group, Route):
                    placeobject.partof = group
                    group.points.insert(position + self.points_added, placeobject)
                else:
                    placeobject.partof = route_container[group]
                    route_container[group].points.insert(position + self.points_added, placeobject)
                self.points_added += 1
            elif isinstance(object, libkmp.MapObject):
                self.level_file.objects.objects.append(placeobject)
                placeobject.set_route_info()
                if placeobject.route_obj is not None:
                    placeobject.route_obj.used_by.append(placeobject)
            elif isinstance(object, libkmp.KartStartPoint):
                self.level_file.kartpoints.positions.append(placeobject)
                if len(self.level_file.kartpoints.positions) == 1:
                    #copy over the thing
                    placeobject.pole_position = self.level_file.pole_position
                    placeobject.start_squeeze = self.level_file.start_squeeze
            elif isinstance(object, libkmp.JugemPoint):
                self.level_file.respawnpoints.append(placeobject)
                if group:
                    self.level_file.reassign_one_respawn(placeobject)
                self.level_file.rotate_one_respawn(placeobject)
            elif isinstance(object, libkmp.Area):
                if placeobject.type == 0:
                    self.level_file.replayareas.append(placeobject)
                    if placeobject.camera is not None:
                        placeobject.camera.used_by.append(placeobject)
                else:
                    self.level_file.areas.append(placeobject)
                    if placeobject.type == 3:
                        self.auto_route_obj(placeobject)
                        self.object_to_be_added = [object, group, position]
                    elif placeobject.type == 4:
                        placeobject.find_closest_enemypoint()
                        #assign to closest enemypoint
            elif isinstance(object, libkmp.OpeningCamera):
                self.level_file.cameras.append(placeobject)
            elif isinstance(object, libkmp.ReplayCamera):
                self.level_file.replaycameras.append(placeobject)
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

        added_area = -1
        for object, group, position in self.objects_to_be_added:
            if isinstance(object, libkmp.Area):
                added_area = object.type

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
                try:
                    placeobject = object.copy()
                except:
                    placeobject = deepcopy(object)
                placed_objects.append(placeobject)

                if hasattr(placeobject, "position"):
                    placeobject.position = Vector3(x, y, z)

                if isinstance(object, (libkmp.EnemyPoint, libkmp.ItemPoint)):
                    to_deal_with = self.level_file.get_to_deal_with(object)
                    to_deal_with.groups[group].points.insert(position + self.points_added, placeobject)
                    self.points_added += 1
                    if to_deal_with.num_total_points() == 255:
                        self.button_stop_adding()

                elif isinstance(object, libkmp.RoutePoint):
                    route_container = self.level_file.get_route_container(object.partof)
                    if isinstance(group, Route):
                        placeobject.partof = group
                        group.points.insert(position + self.points_added, placeobject)
                    else:
                        placeobject.partof = route_container[group]
                        route_container[group].points.insert(position + self.points_added, placeobject)
                    self.points_added += 1
                elif isinstance(object, libkmp.MapObject):
                    self.level_file.objects.objects.append(placeobject)
                elif isinstance(object, libkmp.KartStartPoint):
                    self.level_file.kartpoints.positions.append(placeobject)
                elif isinstance(object, libkmp.JugemPoint):
                    self.level_file.respawnpoints.append(placeobject)
                    if group:
                        self.level_file.reassign_one_respawn(object)
                elif isinstance(object, libkmp.Area):
                    if object.type == 0:
                        self.level_file.replayareas.append(placeobject)
                    else:
                        self.level_file.areas.append(placeobject)
                elif isinstance(object, libkmp.OpeningCamera):
                    self.level_file.cameras.append(placeobject)
                elif isinstance(object, libkmp.ReplayCamera):
                    self.level_file.replaycameras.append(placeobject)
                elif isinstance(object, Route):
                    if added_area == 0:
                        self.level_file.replaycameraroutes.append(placeobject)
                    else:
                        route_container = self.level_file.get_route_container(object)
                        route_container.append(placeobject)
                else:
                    raise RuntimeError("Unknown object type {0}".format(type(object)))

        for object in placed_objects:
            if isinstance(object, libkmp.OpeningCamera):
                object.position.y += 1000
                if object.type in routed_cameras:
                    object.route_obj = self.level_file.cameraroutes[-1]
                    object.route_obj.used_by.append(object)
                    for point in object.route_obj.points:
                        point.position = point.position + object.position
                        self.action_ground_spec_object(point)
            if isinstance(object, libkmp.ReplayCamera):
                object.position.y += 1000
                object.position.x += 3000
                if object.type in routed_cameras:
                    object.route_obj = self.level_file.replaycameraroutes[-1]
                    object.route_obj.used_by.append(object)

                    object.route_obj.points[0].position = object.position
                    object.route_obj.points[1].position = Vector3( object.position.x, object.position.y, object.position.z - 3500)
            if isinstance(object, libkmp.Area):
                if object.type == 0:
                    object.camera = self.level_file.replaycameras[-1]
                    self.level_file.replaycameras[-1].used_by.append(object)
                elif object.type == 3:
                    object.route_obj =self.level_file.routes[-1]
                    object.route_obj.used_by.append(object)
                    for point in object.route_obj.points:
                        point.position = point.position + object.position
                        self.action_ground_spec_object(point)
                elif object.type == 9:
                    object.position.z += 300
            if isinstance(object, Route):

                for point in object.points:
                    self.action_ground_spec_object(point)
            if isinstance(object, libkmp.MapObject):

                object.route_obj = self.level_file.routes[-1]
                object.route_obj.used_by.append(object)

                for point in object.route_obj.points:
                    point.position = point.position + placeobject.position
                    self.action_ground_spec_object(point)

        self.pik_control.update_info()
        self.level_view.do_redraw()
        self.leveldatatreeview.set_objects(self.level_file)
        self.set_has_unsaved_changes(True)

    @catch_exception
    def action_move_objects(self, deltax, deltay, deltaz):

        added_pos = []

        for pos in self.level_view.selected_positions:
            if pos not in added_pos:
                pos.x += deltax
                pos.y += deltay
                pos.z += deltaz

                added_pos.append(pos)

            self.level_view.gizmo.move_to_average(self.level_view.selected_positions)

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

        #C IS FOR "connecting"
        #
        if event.key() == Qt.Key_C and len(self.level_view.selected) == 1:
            sel_obj = self.level_view.selected[0]
            if isinstance(sel_obj, Checkpoint):
                self.connect_start = self.level_view.selected[0]
                self.level_view.connecting_mode = True
                self.level_view.connecting_start = self.connect_start.get_mid()
            elif isinstance( sel_obj , (KMPPoint, MapObject, OpeningCamera, Area) ):
                if isinstance(sel_obj, MapObject) and sel_obj.route_info is None:
                    return
                if isinstance(sel_obj, Area) and sel_obj.type not in [0, 3, 4]:
                    return
                self.connect_start = self.level_view.selected[0]
                self.level_view.connecting_mode = True
                self.level_view.connecting_start = self.connect_start.position
        elif event.key() == Qt.Key_B and self.level_view.selected:
            if self.select_start is not None:
                self.select_start = [x for x in self.level_view.selected]

            pass
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
            self.level_view.connecting_start = None
            self.connect_start = None
            self.connect_mode = None
        if event.key() == Qt.Key_B:
            self.select_start = None

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
                self.level_file.enemypointgroups.remove_point(obj)
            if isinstance(obj, libkmp.ItemPoint):
                self.level_file.itempointgroups.remove_point(obj)

            elif isinstance(obj, libkmp.RoutePoint):
                #route_container = self.level_file.get_route_container(obj.partof)
                #do not allow used route to fall under 2 points
                not_used = not obj.partof.used_by
                not_used |= all( (x in self.level_view.selected) for x in obj.partof.used_by )
                if len(obj.partof.points) > 2 or not_used:
                    obj.partof.points.remove(obj)

                    if len(obj.partof.points) == 0:
                        route_container = self.level_file.get_route_container(obj.partof)

                        for object in obj.partof.used_by:
                            object.route_obj = None
                        route_container.remove(obj.partof)

            elif isinstance(obj, libkmp.Checkpoint):
                self.level_file.checkpoints.remove_point(obj)

            elif isinstance(obj, libkmp.MapObject):
                self.level_file.remove_object(obj)
            elif isinstance(obj, libkmp.KartStartPoint):
                self.level_file.kartpoints.positions.remove(obj)
            elif isinstance(obj, libkmp.JugemPoint):
                self.level_file.remove_respawn(obj)
                #self.level_file.respawnpoints.remove(obj)
            elif isinstance(obj, libkmp.Area):
                if obj.type == 0:
                    self.level_file.replayareas.remove_area(obj)
                else:
                    self.level_file.areas.remove_area(obj)
            elif isinstance(obj, libkmp.Camera):
                if isinstance(obj, libkmp.OpeningCamera):
                    self.level_file.remove_camera(obj)
            elif isinstance(obj, PointGroup ):
                self.level_file.remove_group(obj)

            elif isinstance(obj, libkmp.Route):
                route_container = self.level_file.get_route_container(obj)

                for object in obj.used_by:
                    object.route_obj = None
                route_container.remove(obj)

        self.level_view.selected = []
        self.level_view.selected_positions = []
        self.level_view.selected_rotations = []

        self.pik_control.reset_info()
        self.leveldatatreeview.set_objects(self.level_file)
        self.level_view.gizmo.hidden = True
        #self.pikmin_gen_view.update()
        self.level_view.do_redraw()
        self.set_has_unsaved_changes(True)

    def update_route_used_by(self, objs, old, new):
        #print("update route used by", obj, old, new)
        if old == new:
            return
        if old is not None:
            for obj in objs:
                old.used_by.remove(obj)
        if new is not None:
            for obj in objs:
                new.used_by.append(obj)

    def update_camera_used_by(self, objs, old : Camera, new : Camera):
        #print("update route used by", obj, old, new)
        if old == new:
            return
        if old is not None:
            for obj in objs:
                old.used_by.remove(obj)
        if new is not None:
            for obj in objs:
                new.used_by.append(obj)

    def on_cut_action_triggered(self):
        self.on_copy_action_triggered()
        self.action_delete_objects()

    def on_copy_action_triggered(self):
        # Widgets are unpickleable, so they need to be temporarily stashed. This needs to be done
        # recursively, as top-level groups main contain points associated with widgets too.

        object_to_widget = {}
        object_to_usedby = {}
        object_to_partof = {}
        object_to_routeobj = {}
        object_to_enemypoint = {}
        object_to_camera = {}
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
            if hasattr(obj, 'route_obj'):
                object_to_routeobj[obj] = obj.route_obj
                obj.route = obj.set_route( self.level_file.cameras.get_routes() + self.level_file.replayareas.get_routes()  )
                obj.route_obj = None
            if hasattr(obj, 'enemypoint'):
                object_to_enemypoint[obj] = obj.enemypoint
                obj.enemypointid = obj.set_enemypointid()
                obj.enemypoint = None
            if hasattr(obj, 'camera'):
                object_to_camera[obj] = obj.camera
                obj.cameraid = obj.set_camera()
                obj.camera = None

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
            for obj, route_obj in object_to_routeobj.items():
                obj.route_obj = route_obj
            for obj, enemypoint in object_to_enemypoint.items():
                obj.enemypoint = enemypoint
            for obj, camera in object_to_camera.items():
                obj.camera = camera
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
            if isinstance(obj, libkmp.Route):
                obj.used_by = []
                route_container = self.level_file.get_route_container(obj.partof)
                route_container.append(obj)
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
                        new_route = self.level_file.get_route_for_obj(obj)
                        route_container = self.level_file.get_route_container(new_route)
                        route_container.append(new_route)
                    target_route = self.level_file.routes[-1]

                if target_route is not None:
                    obj.partof = target_route
                target_route.points.append(obj)

            # Autonomous objects.
            elif isinstance(obj, libkmp.MapObject):
                self.level_file.objects.objects.append(obj)
                if obj.route != -1:
                    obj.route_obj = self.level_file.routes[obj.route]
            elif isinstance(obj, libkmp.KartStartPoint):
                self.level_file.kartpoints.positions.append(obj)
            elif isinstance(obj, libkmp.JugemPoint):

                self.level_file.respawnpoints.append(obj)
            elif isinstance(obj, libkmp.Area):
                if obj.type == 0:
                    self.level_file.replayareas.append(obj)
                else:
                    self.level_file.areas.append(obj)
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

                elif False and isinstance(currentobj, libkmp.RoutePoint):

                    to_look_through = self.leveldatatreeview.objectroutes if isinstance(currentobj.partof, libkmp.ObjectRoute) else self.leveldatatreeview.cameraroutes
                    for i in range(to_look_through.childCount()):
                        child = to_look_through.child(i)
                        item = get_treeitem(child, currentobj)
                        if item is not None:
                            break

                elif isinstance(currentobj, libkmp.MapObject):
                    item = get_treeitem(self.leveldatatreeview.objects, currentobj)
                elif isinstance(currentobj, libkmp.OpeningCamera):
                    item = get_treeitem(self.leveldatatreeview.cameras, currentobj)
                elif isinstance(currentobj, libkmp.Area):
                    if currentobj.type == 0:
                        item = get_treeitem(self.leveldatatreeview.replayareas, currentobj)
                    else:
                        item = get_treeitem(self.leveldatatreeview.areas, currentobj)
                elif isinstance(currentobj, libkmp.JugemPoint):
                    item = get_treeitem(self.leveldatatreeview.respawnpoints, currentobj)
                elif isinstance(currentobj, libkmp.KartStartPoint):
                    item = get_treeitem(self.leveldatatreeview.kartpoints, currentobj)
                elif isinstance(currentobj, libkmp.CannonPoint):
                    item = get_treeitem(self.leveldatatreeview.cannonpoints, currentobj)
                #assert item is not None

                # Temporarily suppress signals to prevent both checkpoints from
                # being selected when just one checkpoint is selected in 3D view.
                suppress_signal = False
                if (isinstance(currentobj, libkmp.Checkpoint)
                    and (currentobj.start in self.level_view.selected_positions
                         or currentobj.end in self.level_view.selected_positions)):
                    suppress_signal = True

                if suppress_signal:
                    self.leveldatatreeview.blockSignals(True)

                if item is not None:
                    self.leveldatatreeview.setCurrentItem(item)
                self.pik_control.set_buttons(currentobj)

                if suppress_signal:
                    self.leveldatatreeview.blockSignals(False)

            #if nothing is selected and the currentitem is something that can be selected
            #clear out the buttons
            curr_item = self.leveldatatreeview.currentItem()
            if (not selected) and (curr_item is not None) and hasattr(curr_item, "bound_to"):
                bound_to_obj = curr_item.bound_to
                if bound_to_obj and hasattr(bound_to_obj, "position"):
                    self.pik_control.set_buttons(None)
    @catch_exception
    def action_update_info(self):
        self.pik_control.reset_info()
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

            elif len(selected) == 0:
                #if self.leveldatatreeview.cameras.isSelected():
                #    self.pik_control.set_info(self.leveldatatreeview.cameras.bound_to, self.update_3d)
                #    self.pik_control.update_info()
                if self.leveldatatreeview.kartpoints.isSelected():
                    self.pik_control.set_info(self.leveldatatreeview.kartpoints.bound_to, self.update_3d)
                    self.pik_control.update_info()
                else:
                    self.pik_control.reset_info()

            else:

                self.pik_control.set_info_multiple(selected, self.update_3d)
                #self.pik_control.reset_info("{0} objects selected".format(len(self.level_view.selected)))
                self.pik_control.set_objectlist(selected)
                self.pik_control.update_info()

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

        if len(self.level_view.selected) == 1:
            obj = self.level_view.selected[0]
            if isinstance(obj, RoutePoint):
                select_all = QAction("Select All in Route", self)
                select_all.triggered.connect(lambda: self.select_route_from_point(obj))
                context_menu.addAction(select_all)

                delete_all = QAction("Delete Route", self)
                delete_all.triggered.connect(lambda: self.delete_route_from_point(obj))
                context_menu.addAction(delete_all)
            if isinstance(obj, Camera) and obj in self.level_file.cameras:
                set_first = QAction("Make First Cam", self)
                set_first.triggered.connect(lambda: self.make_first_cam(obj))
                context_menu.addAction(set_first)

                select_linked = QAction("Select Linked", self)
                select_linked.triggered.connect(lambda: self.select_linked(obj))
                context_menu.addAction(select_linked)

            if isinstance(obj, Area) and obj in self.level_file.replayareas:
                select_linked = QAction("Select Linked", self)
                select_linked.triggered.connect(lambda: self.select_linked(obj))
                context_menu.addAction(select_linked)
            if isinstance(obj, EnemyPoint) or isinstance(obj, ItemPoint):
                set_as_first = QAction("Set as First", self)
                set_as_first.triggered.connect(lambda: self.set_as_first(obj))
                context_menu.addAction(set_as_first)

                select_all_group = QAction("Select All in Group", self)
                select_all_group.triggered.connect(lambda: self.select_all_of_group(obj))
                context_menu.addAction(select_all_group)

                delete_all_group = QAction("Delete All in Group", self)
                delete_all_group.triggered.connect(lambda: self.delete_all_of_group(obj))
                context_menu.addAction(delete_all_group)
            if isinstance(obj, MapObject):
                select_type = QAction("Select All of Type", self)
                select_type.triggered.connect(lambda: self.select_all_of_type(obj))
                context_menu.addAction(select_type)

        context_menu.exec(self.sender().mapToGlobal(position))
        context_menu.destroy()



    def action_copy_coords_to_clipboard(self):
        if self.current_coordinates is not None:
            QApplication.clipboard().setText(", ".join(str(x) for x in self.current_coordinates))

    def select_route_from_point(self, obj : RoutePoint):
        route : Route = obj.partof
        self.level_view.selected = route.points
        self.level_view.selected_positions =  [point.position for point in route.points]
        self.level_view.selected_rotations = []

        self.level_view.gizmo.move_to_average(self.level_view.selected_positions)
        self.level_view.do_redraw()
        self.level_view.select_update.emit()

    def delete_route_from_point(self, obj : RoutePoint):
        route : Route = obj.partof
        self.level_view.selected = [route]
        self.action_delete_objects()
        self.level_view.do_redraw()
        self.level_view.select_update.emit()

    def make_first_cam(self, obj: Camera):
        self.level_file.cameras.startcam = obj
        self.level_view.level_file = self.level_file
        self.level_view.do_redraw()

    def select_linked(self, obj):
        if isinstance(obj, Area) and obj in self.level_file.replayareas:
            new_selected = [obj]
            new_selected_position = [obj.position]
            if obj.camera is not None:
                new_selected.append(obj.camera)
                new_selected_position.append(obj.camera.position)
            if obj.camera.route_obj is not None:
                new_selected.extend( [ point for point in obj.camera.route_obj.points]  )
                new_selected_position.extend( [ point.position for point in obj.camera.route_obj.points]  )

            self.level_view.selected = new_selected
            self.level_view.selected_positions = new_selected_position
            self.level_view.selected_rotations = [obj.rotation]
            self.level_view.do_redraw()
            self.level_view.select_update.emit()
        elif isinstance(obj, Camera):
            new_selected = [obj]
            new_selected_position = [obj.position]
            if obj.route_obj is not None:
                new_selected.extend( obj.route_obj.points  )
                new_selected_position.extend( [ point.position for point in obj.route_obj.points]  )

            self.level_view.selected = new_selected
            self.level_view.selected_positions = new_selected_position
            self.level_view.selected_rotations = [obj.rotation]
            self.level_view.do_redraw()
            self.level_view.select_update.emit()

    def set_as_first(self, obj):
        to_deal_with = self.level_file.get_to_deal_with(obj)
        to_deal_with.set_this_as_first(obj)

    def action_update_position(self, event, pos):
        self.current_coordinates = pos

        y_coord = f"{pos[1]:.2f}" if pos[1] is not None else "-"

        display_string = f"🖱️ ({pos[0]:.2f}, {y_coord}, {pos[2]:.2f})"

        selected = self.level_view.selected
        if len(selected) == 1 and hasattr(selected[0], "position"):

            obj_pos = selected[0].position
            display_string += f"   📦 ({obj_pos.x:.2f}, {obj_pos.y:.2f}, {obj_pos.z:.2f})"

            if self.level_view.collision is not None:
                height = self.level_view.collision.collide_ray_closest(obj_pos.x, obj_pos.z, obj_pos.y)
                if height is not None:
                    display_string += f"   📏 {obj_pos.y - height:.2f}"

        self.statusbar.showMessage(display_string)
        self.update_3d()


    def action_connectedto_end(self):

        if self.connect_start is not None and self.level_view.connecting_mode:
            self.ready_to_connect = True
        else:
            self.ready_to_connect = False

    def action_connectedto_final(self):
        if not self.ready_to_connect or self.connect_start is None:
            return
        self.ready_to_connect = False


        if len(self.level_view.selected) == 0:
            #create a new enemy/item/checkpoint group
            if isinstance(self.connect_start, KMPPoint):

                to_deal_with = self.level_file.get_to_deal_with(self.connect_start)
                start_groupind, start_group, start_pointind = to_deal_with.find_group_of_point(self.connect_start)
                if start_group is None:
                    print("start group is none, this shouldn't happen", self.connect_start.position)
                    return
                if start_group.num_next() == 6:
                    return
                point_to_add = to_deal_with.get_new_point()
                group_to_add = to_deal_with.get_new_group()
                if start_pointind == len(start_group.points) - 1:
                    to_deal_with.groups.append(group_to_add)

                    group_to_add.add_new_prev(start_group)
                    start_group.add_new_next(group_to_add)

                    self.object_to_be_added = [point_to_add, len(to_deal_with.groups) - 1, 0 ]
                else:
                    self.split_group( start_group, self.connect_start )
                    to_deal_with.groups.append(group_to_add)

                    group_to_add.add_new_prev(start_group)
                    start_group.add_new_next(group_to_add)

                    self.object_to_be_added = [point_to_add, len(to_deal_with.groups) - 1, 0 ]

                start_group.remove_next(start_group)
                start_group.remove_prev(start_group)

                self.pik_control.button_add_object.setChecked(True)
                self.level_view.set_mouse_mode(mkwii_widgets.MOUSE_MODE_ADDWP)
            #create a new path for the object/camera
            elif isinstance(self.connect_start, (MapObject, Camera) ):
                if self.connect_start.route_obj is not None and self.connect_mode == 1:
                    if isinstance(self.connect_start, MapObject ):
                        self.button_add_from_addi_options(5, self.connect_start)
                    elif isinstance(self.connect_start, Camera ):
                        self.button_add_from_addi_options(5.5, self.connect_start)

                    route_container = self.level_file.get_route_container(self.connect_start)
                    new_group = route_container[-1]

                    self.connect_start.route_obj = new_group
                    new_group.used_by.append(self.connect_start)

                    self.button_add_from_addi_options(6, new_group)
        elif len(self.level_view.selected) != 1:
            return
        else: #len(self.level_view.selected) == 1
            endpoint = self.level_view.selected[0]
            to_deal_with = None
            if isinstance(endpoint, KMPPoint) and isinstance(self.connect_start, KMPPoint):
                if isinstance(endpoint, EnemyPoint) and isinstance(self.connect_start, EnemyPoint):
                    to_deal_with = self.level_file.enemypointgroups
                elif isinstance(endpoint, ItemPoint) and isinstance(self.connect_start, ItemPoint):
                    to_deal_with = self.level_file.itempointgroups
                elif isinstance(endpoint, Checkpoint) and isinstance(self.connect_start, Checkpoint):
                    to_deal_with = self.level_file.checkpoints

                if to_deal_with is not None:
                    self.connect_two_groups(endpoint, to_deal_with)
            elif isinstance(endpoint, JugemPoint) and isinstance(self.connect_start, Checkpoint):
                self.connect_start.respawn_obj = endpoint
            elif isinstance(endpoint, RoutePoint) and isinstance(self.connect_start, (MapObject, Camera)):
                if isinstance(endpoint.partof, ObjectRoute) and isinstance(self.connect_start, MapObject):
                    if self.connect_start.route_obj is not None:
                        self.connect_start.route_obj.used_by.remove(self.connect_start)
                    self.connect_start.route_obj = endpoint.partof
                    endpoint.partof.used_by.append(self.connect_start)
                if isinstance(endpoint.partof, CameraRoute) and isinstance(self.connect_start, Camera):
                    if self.connect_start.route_obj is not None:
                        self.connect_start.route_obj.used_by.remove(self.connect_start)
                    self.connect_start.route_obj = endpoint.partof
                    endpoint.partof.used_by.append(self.connect_start)
            elif isinstance(self.connect_start, Area):
                area : Area = self.connect_start
                if self.connect_start.type == 0 and isinstance(endpoint, Camera):
                    old_camera = area.camera
                    area.camera = endpoint
                    self.update_camera_used_by(area, old_camera, area.camera )
                    if not old_camera.used_by:
                        self.level_file.remove_camera(old_camera)
                if self.connect_start.type == 3 and isinstance(endpoint, RoutePoint) and isinstance(endpoint.partof, AreaRoute):
                    old_route = area.route_obj
                    area.route_obj = endpoint.partof
                    self.update_route_used_by([area], old_route, area.route_obj)
                elif self.connect_start.type == 4 and isinstance(endpoint, EnemyPoint):
                    self.connect_start.enemypoint = endpoint
            elif isinstance(endpoint, Camera) and isinstance(self.connect_start, Camera):
                if (endpoint in self.level_file.cameras) and (self.connect_start in self.level_file.cameras):
                    self.connect_start.nextcam_obj = endpoint

        self.connect_start = None
        self.select_start = None

        self.leveldatatreeview.set_objects(self.level_file)
        self.update_3d()
        self.set_has_unsaved_changes(True)

    def connect_two_groups(self, endpoint, to_deal_with : PointGroups):
        if endpoint == self.connect_start:
            return

        end_groupind, end_group, end_pointind = to_deal_with.find_group_of_point(endpoint)

        start_groupind, start_group, start_pointind = to_deal_with.find_group_of_point(self.connect_start)
        #print( end_groupind, end_group, end_pointind )
        #print( start_groupind, start_group, start_pointind  )
        #make sure that start_group is good to add another
        if start_group.num_next() == 6:
            return

        #if drawing from an endpoint to a startpoint of the next group
        if (start_pointind + 1 == len(start_group.points) and end_pointind == 0):
            #if a link already exists, remove it
            if end_group in start_group.nextgroup:
                start_group.remove_next(end_group)
                end_group.remove_prev(start_group)
                to_deal_with.merge_groups()
            else:
                if end_group.num_prev() < 6 and start_group.num_next() < 6:
                    start_group.add_new_next( end_group  )
                    end_group.add_new_prev(start_group)
                if end_group != start_group:
                    start_group.remove_next(start_group)
                    start_group.remove_prev(start_group)
            return

        self.split_group( start_group, self.connect_start )
        group_1 = to_deal_with.groups[-1]

        if start_groupind == end_groupind and end_pointind > start_pointind:
            new_idx = end_pointind - 1 - len(group_1.points)
            self.split_group( group_1, group_1.points[new_idx])
        else:
            self.split_group( end_group, end_group.points[end_pointind - 1])

        group_2 = to_deal_with.groups[-1]

        #remove self connections, if they exist
        start_group.remove_next(start_group)
        start_group.remove_prev(start_group)

        if start_groupind == end_groupind and end_pointind < start_pointind:
            group_1.add_new_prev(group_2)
            group_2.add_new_next(group_2)
        else:
            start_group.add_new_next(group_2)
            group_2.add_new_prev(start_group)

    def set_and_start_copying(self):
        #print(self.level_view.selected)
        #print(isinstance( self.level_view.selected[0], (MapObject, Area, Camera)))
        if len(self.level_view.selected) == 1 and isinstance( self.level_view.selected[0], (MapObject, Area, Camera)):
            self.obj_to_copy = self.level_view.selected[0]
            self.copy_current_obj()

    def copy_current_obj(self, new_route = True):
        if self.obj_to_copy is not None:
            self.object_to_be_added = None

            map_check = isinstance(self.obj_to_copy, MapObject) and self.obj_to_copy.route_info is not None
            cam_check = isinstance(self.obj_to_copy, Camera) and self.obj_to_copy.type in routed_cameras
            area_check = isinstance(self.obj_to_copy, Area) and self.obj_to_copy.type == 3
            #if isinstance(self.obj_to_copy, libkmp.MapObject) and self.obj_to_copy.route_info == 2:
            if new_route and ( map_check or cam_check or area_check):

                self.objects_to_be_added = []
                new_route = self.level_file.get_route_for_obj(self.obj_to_copy)
                route_container = self.level_file.get_route_container(self.obj_to_copy)

                if self.obj_to_copy.route_obj is not None :
                    for point in self.obj_to_copy.route_obj .points:
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


    def auto_generation(self):
        self.level_file.auto_generation()
        self.leveldatatreeview.set_objects(self.level_file)
        self.leveldatatreeview.bound_to_group(self.level_file)
        self.level_view.do_redraw()
        self.update_3d()

    def auto_cleanup(self):
        self.level_file.auto_cleanup()
        self.leveldatatreeview.set_objects(self.level_file)
        self.leveldatatreeview.bound_to_group(self.level_file)
        self.level_view.do_redraw()
        self.update_3d()

    def dragEnterEvent(self, event):
        mime_data = event.mimeData()
        if mime_data.hasUrls:
            url = mime_data.urls()[0]
            filepath = url.toLocalFile()
            exten = filepath[filepath.rfind("."):].lower()
            if exten in [".kmp", ".kcl"]:
                event.acceptProposedAction()

    def dropEvent(self, event):
        mime_data = event.mimeData()
        if mime_data.hasUrls:
            url = mime_data.urls()[0]
            filepath = url.toLocalFile()
            exten = filepath[filepath.rfind("."):].lower()
            if exten == ".kmp":
                self.button_load_level( False, filepath, add_to_ini = False)
            elif exten == ".kcl":
                self.load_collision_kcl(filepath)

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
    app.setStyle(QtWidgets.QStyleFactory.create("Fusion"))


    role_colors = []
    role_colors.append((QtGui.QPalette.Window, QtGui.QColor(60, 60, 60)))
    role_colors.append((QtGui.QPalette.WindowText, QtGui.QColor(200, 200, 200)))
    role_colors.append((QtGui.QPalette.Base, QtGui.QColor(25, 25, 25)))
    role_colors.append((QtGui.QPalette.AlternateBase, QtGui.QColor(60, 60, 60)))
    role_colors.append((QtGui.QPalette.ToolTipBase, QtGui.QColor(40, 40, 40)))
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

    QtWidgets.QToolTip.setPalette(palette)
    padding = app.fontMetrics().height() // 2
    app.setStyleSheet(f'QToolTip {{ padding: {padding}px; }}')

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