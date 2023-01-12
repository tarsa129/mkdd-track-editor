import traceback
from io import StringIO
from itertools import chain
from math import acos, pi
import os
import sys

from PyQt5.QtGui import QMouseEvent, QWheelEvent, QPainter, QColor, QFont, QFontMetrics, QPolygon, QImage, QPixmap, QKeySequence
from PyQt5.QtWidgets import (QWidget, QListWidget, QListWidgetItem, QDialog, QMenu, QLineEdit, QFileDialog, QScrollArea,
                            QMdiSubWindow, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QTextEdit, QAction, QShortcut)
import PyQt5.QtWidgets as QtWidgets
import PyQt5.QtCore as QtCore
from PyQt5.QtCore import QSize, pyqtSignal, QPoint, QRect
from PyQt5.QtCore import Qt
import PyQt5.QtGui as QtGui

import lib.libbol as libbol
from widgets.data_editor import choose_data_editor, ObjectEdit
from lib.libbol import get_full_name


def catch_exception(func):
    def handle(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            QtWidgets.QApplication.quit()
        except:
            traceback.print_exc()
            #raise
    return handle


def catch_exception_with_dialog(func):
    def handle(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            traceback.print_exc()
            open_error_dialog(str(e), None)
    return handle


def catch_exception_with_dialog_nokw(func):
    def handle(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            traceback.print_exc()
            open_error_dialog(str(e), None)
    return handle


def open_error_dialog(errormsg, self):
    errorbox = QtWidgets.QMessageBox()
    errorbox.critical(self, "Error", errormsg)
    errorbox.setFixedSize(500, 200)


class ErrorAnalyzer(QDialog):

    @catch_exception
    def __init__(self, bol, *args, **kwargs):
        super().__init__(*args, **kwargs)
        font = QFont()
        font.setFamily("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setFixedPitch(True)
        font.setPointSize(10)

        self.setWindowTitle("Analysis Results")
        self.text_widget = QTextEdit(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.text_widget)

        self.setMinimumSize(QSize(300, 300))
        self.text_widget.setFont(font)
        self.text_widget.setReadOnly(True)

        width = self.text_widget.fontMetrics().averageCharWidth() * 80
        height = self.text_widget.fontMetrics().height() * 20
        self.resize(width, height)

        lines = ErrorAnalyzer.analyze_bol(bol)
        if not lines:
            text = "No known common errors detected!"
        else:
            text ='\n\n'.join(lines)
        self.text_widget.setText(text)

    @classmethod
    @catch_exception
    def analyze_bol(cls, bol: libbol.BOL) -> 'list[str]':
        lines: list[str] = []

        def write_line(line):
            lines.append(line)

        # Check enemy point linkage errors
        links = {}
        for group_index, group in enumerate(bol.enemypointgroups.groups):
            for i, point in enumerate(group.points):
                if point.link == -1:
                    continue

                if point.link not in links:
                    links[point.link] = [(group_index, i, point)]
                else:
                    links[point.link].append(((group_index, i, point)))

        for link_id, points in links.items():
            if len(points) == 1:
                group_index, i, point = points[0]
                write_line("Point {0} in enemy point group {1} has link {2}; No other point has link {2}".format(
                    i, group_index, point.link
                ))
        for group_index, group in enumerate(bol.enemypointgroups.groups):
            if not group.points:
                write_line("Empty enemy path {0}.".format(group_index))
                continue

            if group.points[0].link == -1:
                write_line("Start point of enemy point group {0} has no valid link to form a loop".format(group_index))
            if group.points[-1].link == -1:
                write_line("End point of enemy point group {0} has no valid link to form a loop".format(group_index))

        # Check enemy paths unique ID.
        enemy_paths_ids = {}
        for enemy_path_index, enemy_path in enumerate(bol.enemypointgroups.groups):
            if enemy_path.id in enemy_paths_ids:
                write_line(f"Enemy path {group_index} using ID {enemy_path.id} that is already "
                           f"used by enemy path {enemy_paths_ids[enemy_path.id]}.")
            else:
                enemy_paths_ids[enemy_path.id] = enemy_path_index

        # Check prev/next groups of checkpoints
        for i, group in enumerate(bol.checkpoints.groups):
            for index in chain(group.prevgroup, group.nextgroup):
                if index != -1:
                    if index < -1 or index+1 > len(bol.checkpoints.groups):
                        write_line("Checkpoint group {0} has invalid Prev or Nextgroup index {1}".format(
                            i, index
                        ))

        #check for empty (and used!) routes
        for i, group in enumerate(bol.routes):
            
            if len(group.used_by) > 0 :
                if len(group.points) == 0:
                    write_line("Route {0} is used, but does not have any points".format( i ))
                elif len(group.points) == 1:  
                    write_line("Route {0} is used, but only has one point".format( i ))

        # Validate path id in objects
        for object in bol.objects.objects:
            if object.route < -1 or object.route + 1 > len(bol.routes):
                write_line("Map object {0} uses path id {1} that does not exist".format(
                    get_full_name(object.objectid), object.route
                ))

        # Validate Kart start positions
        if len(bol.kartpoints.positions) == 0:
            write_line("Map contains no kart start points")
        else:
            exist = [False for x in range(8)]

            for i, kartstartpos in enumerate(bol.kartpoints.positions):
                if kartstartpos.playerid == 0xFF:
                    if all(exist):
                        write_line("Duplicate kart start point for all karts")
                    exist = [True for x in range(8)]
                elif kartstartpos.playerid > 8:
                    write_line("A kart start point with an invalid player id exists: {0}".format(
                        kartstartpos.playerid
                    ))
                elif exist[kartstartpos.playerid]:
                    write_line("Duplicate kart start point for player id {0}".format(
                        kartstartpos.playerid))
                else:
                    exist[kartstartpos.playerid] = True

        # Check camera indices in areas
        for i, area in enumerate(bol.areas.areas):
            if area.camera_index < -1 or area.camera_index + 1 > len(bol.cameras):
                write_line("Area {0} uses invalid camera index {1}".format(i, area.camera_index))
            elif area.area_type == 1 and area.camera_index == -1:
                write_line("Area {0} uses invalid camera index {1}".format(i, area.camera_index))

        have_start = False
        first_start = -1
        # Check cameras
        for i, camera in enumerate(bol.cameras):
            if camera.nextcam < -1 or camera.nextcam + 1 > len(bol.cameras):
                write_line("Camera {0} uses invalid nextcam (next camera) index {1}".format(
                    i, camera.nextcam
                ))
            if camera.route < -1 or camera.route + 1 > len(bol.cameraroutes):
                write_line("Camera {0} uses invalid path id {1}".format(i, camera.route))
            if camera.camtype == 1 and camera.route < 0:
                write_line("Camera {0} uses invalid path id {1}".format(i, camera.route))
            
            if camera.startcamera != 0 and not have_start:
                first_start = i
                have_start = True
            elif camera.startcamera != 0 and have_start:
                write_line("Camera {0} is a starting cam, but Camera {1} is already a starting cam".format(i, first_start))
        
        
        if len(bol.checkpoints.groups) == 0:
            write_line("You need at least one checkpoint group!")

        if len(bol.enemypointgroups.groups) == 0:
            write_line("You need at least one enemy point group!")

        cls.check_checkpoints_convex(bol, write_line)

        return lines

    @classmethod
    def check_checkpoints_convex(cls, bol, write_line):
        for gindex, group in enumerate(bol.checkpoints.groups):
            if len(group.points) > 1:
                for i in range(1, len(group.points)):
                    c1 = group.points[i-1]
                    c2 = group.points[i]

                    lastsign = None

                    for p1, mid, p3 in ((c1.start, c2.start, c2.end),
                                        (c2.start, c2.end, c1.end),
                                        (c2.end, c1.end, c1.start),
                                        (c1.end, c1.start, c2.start)):
                        side1 = p1 - mid
                        side2 = p3 - mid
                        prod = side1.x * side2.z - side2.x * side1.z
                        if lastsign is None:
                            lastsign = prod > 0
                        else:
                            if not (lastsign == (prod > 0)):
                                write_line("Quad formed by checkpoints {0} and {1} in checkpoint group {2} isn't convex.".format(
                                    i-1, i, gindex
                                ))
                                break


class ErrorAnalyzerButton(QtWidgets.QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.success_icon = QtGui.QIcon('resources/success.svg')
        self.warning_icon = QtGui.QIcon('resources/warning.svg')

        self.setEnabled(False)

        background_color = self.palette().dark().color().name()
        self.setStyleSheet("QPushButton { border: 0px; padding: 2px; } "
                           f"QPushButton:hover {{ background: {background_color}; }}")

    def analyze_bol(self, bol: libbol.BOL):
        print("analyze bol")
        lines = ErrorAnalyzer.analyze_bol(bol)
        if lines:
            self.setIcon(self.warning_icon)
            self.setText(str(len(lines)))
        else:
            self.setIcon(self.success_icon)
            self.setText(str())
        self.setEnabled(True)


class AddPikObjectWindow(QDialog):

    @catch_exception
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "windowtype" in kwargs:
            self.window_name = kwargs["windowtype"]
        else:
            self.window_name = "Add Object"

        width = self.fontMetrics().averageCharWidth() * 80
        height = self.fontMetrics().height() * 42
        self.resize(width, height)
        self.setMinimumSize(QSize(300, 300))

        self.entity = None

        font = QFont()
        font.setFamily("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setFixedPitch(True)
        font.setPointSize(10)


        self.verticalLayout = QVBoxLayout(self)
        self.verticalLayout.setAlignment(Qt.AlignTop)



        self.setup_dropdown_menu()

        self.hbox1 = QHBoxLayout()
        self.hbox2 = QHBoxLayout()


        self.label1 = QLabel(self)
        self.label2 = QLabel(self)
        self.label3 = QLabel(self)
        self.label1.setText("Group")
        self.label2.setText("Position in Group")
        self.label3.setText("(-1 means end of Group)")
        self.group_edit = QLineEdit(self)
        self.position_edit = QLineEdit(self)

        self.label1.setVisible(False)
        self.label2.setVisible(False)
        self.label3.setVisible(False)
        self.group_edit.setVisible(False)
        self.position_edit.setVisible(False)

        self.group_edit.setValidator(QtGui.QIntValidator(0, 2**31-1))
        self.position_edit.setValidator(QtGui.QIntValidator(-1, 2**31-1))

        self.hbox1.setAlignment(Qt.AlignRight)
        self.hbox2.setAlignment(Qt.AlignRight)


        self.verticalLayout.addLayout(self.hbox1)
        self.verticalLayout.addLayout(self.hbox2)
        self.hbox1.addWidget(self.label1)
        self.hbox1.addWidget(self.group_edit)
        self.hbox2.addWidget(self.label2)
        self.hbox2.addWidget(self.position_edit)
        self.hbox2.addWidget(self.label3)

        self.label1.setVisible(False)
        self.label2.setVisible(False)
        self.label3.setVisible(False)
        self.group_edit.setVisible(False)
        self.position_edit.setVisible(False)


        self.editor_widget = None
        self.editor_layout = QScrollArea()#QVBoxLayout(self.centralwidget)
        palette = self.editor_layout.palette()
        palette.setBrush(self.editor_layout.backgroundRole(), palette.dark())
        self.editor_layout.setPalette(palette)
        self.editor_layout.setWidgetResizable(True)
        self.verticalLayout.addWidget(self.editor_layout)
        #self.textbox_xml = QTextEdit(self.centralwidget)
        button_area_layout = QHBoxLayout()
        self.button_savetext = QPushButton(self)
        self.button_savetext.setText("Add Object")
        self.button_savetext.setToolTip("Hotkey: Ctrl+S")
        self.button_savetext.setDisabled(True)
        self.button_savetext.clicked.connect(self.accept)
        button_area_layout.addStretch()
        button_area_layout.addWidget(self.button_savetext)

        self.verticalLayout.addLayout(button_area_layout)
        self.setWindowTitle(self.window_name)
        self.created_object = None
        #QtWidgets.QShortcut(Qt.CTRL + Qt.Key_S, self).activated.connect(self.emit_add_object)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if event.key() == Qt.CTRL + Qt.Key_S:
            self.emit_add_object()
        else:
            super().keyPressEvent(event)

    def emit_add_object(self):
        self.button_savetext.pressed.emit()

    def get_content(self):
        try:
            if not self.group_edit.text():
                group = None
            else:
                group = int(self.group_edit.text())
            if not self.position_edit.text():
                position = None
            else:
                position = int(self.position_edit.text())
            return self.created_object, group, position

        except Exception as e:
            traceback.print_exc()
            open_error_dialog(str(e), self)
            return None

    def setup_dropdown_menu(self):
        self.category_menu = QtWidgets.QComboBox(self)
        self.category_menu.addItem("-- select type --")

        self.verticalLayout.addWidget(self.category_menu)

        self.objecttypes = {
            "Enemy Path": libbol.EnemyPointGroup,
            "Enemy Point": libbol.EnemyPoint,
            "Checkpoint": libbol.Checkpoint,
            "Object Route": libbol.Route,
            "Object Route Point": libbol.RoutePoint,
            "Object": libbol.MapObject,
            "Area": libbol.Area,
            "Camera": libbol.Camera,
            "Respawn Point": libbol.JugemPoint,
            "Kart Start Point": libbol.KartStartPoint,
            
            "Checkpoint Group": libbol.CheckpointGroup,
           
            "Light Param": libbol.LightParam,
            "Minigame Param": libbol.MGEntry
        }

        self.category_menu.addItem("Enemy Path")
        self.category_menu.addItem("Enemy Point")
        self.category_menu.insertSeparator(self.category_menu.count())
        self.category_menu.addItem("Checkpoint Group")
        self.category_menu.addItem("Checkpoint")
        self.category_menu.insertSeparator(self.category_menu.count())
        self.category_menu.addItem("Object Route")
        self.category_menu.addItem("Object Route Point")
        self.category_menu.insertSeparator(self.category_menu.count())
        self.category_menu.addItem("Object")
        self.category_menu.addItem("Kart Start Point")
        self.category_menu.addItem("Area")
        self.category_menu.addItem("Camera")
        self.category_menu.addItem("Respawn Point")
        self.category_menu.insertSeparator(self.category_menu.count())
        self.category_menu.addItem("Light Param")
        self.category_menu.addItem("Minigame Param")

        for i in range(1, self.category_menu.count()):
            text = self.category_menu.itemText(i)
            assert not text or text in self.objecttypes

        self.category_menu.currentIndexChanged.connect(self.change_category)

    def change_category(self, index):
        if index > 0:
            item = self.category_menu.currentText()
            self.button_savetext.setDisabled(False)
            objecttype = self.objecttypes[item]

            if self.editor_widget is not None:
                self.editor_widget.deleteLater()
                self.editor_widget = None
            if self.created_object is not None:
                del self.created_object

            self.created_object = objecttype.new()

            if isinstance(self.created_object, (libbol.Checkpoint, libbol.EnemyPoint, libbol.RoutePoint)):
                self.group_edit.setDisabled(False)
                self.position_edit.setDisabled(False)
                self.group_edit.setVisible(True)
                self.position_edit.setVisible(True)
                self.group_edit.setText("0")
                self.position_edit.setText("-1")

            else:
                self.group_edit.setDisabled(True)
                self.position_edit.setDisabled(True)
                self.group_edit.setVisible(False)
                self.position_edit.setVisible(False)
                self.group_edit.clear()
                self.position_edit.clear()

            data_editor = choose_data_editor(self.created_object)
            if data_editor is not None:
                self.editor_widget = data_editor(self, self.created_object)
                self.editor_widget.layout().addStretch()
                margin = self.fontMetrics().averageCharWidth()
                self.editor_widget.setContentsMargins(margin, margin, margin, margin)
                self.editor_layout.setWidget(self.editor_widget)
                
                
                
                #print("isobject", isinstance(self.editor_widget, ObjectEdit))
                if isinstance(self.editor_widget, ObjectEdit):
                    self.editor_widget.update_data(load_defaults = True)
                    self.editor_widget.set_default_values()
                else:
                    self.editor_widget.update_data()

        else:
            self.editor_widget.deleteLater()
            self.editor_widget = None
            del self.created_object
            self.created_object = None
            self.button_savetext.setDisabled(True)
            self.position_edit.setVisible(False)
            self.group_edit.setVisible(False)

        self.label1.setVisible(self.position_edit.isVisible())
        self.label2.setVisible(self.position_edit.isVisible())
        self.label3.setVisible(self.position_edit.isVisible())

class SpawnpointEditor(QMdiSubWindow):
    triggered = pyqtSignal(object)
    closing = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.centralwidget = QWidget(self)
        self.setWidget(self.centralwidget)
        self.entity = None
        self.resize(400, 200)

        font = QFont()
        font.setFamily("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setFixedPitch(True)
        font.setPointSize(10)
        self.verticalLayout = QVBoxLayout(self.centralwidget)

        self.position = QLineEdit(self.centralwidget)
        self.rotation = QLineEdit(self.centralwidget)

        self.button_savetext = QPushButton(self.centralwidget)
        self.button_savetext.setText("Set Data")
        self.button_savetext.setMaximumWidth(400)

        self.verticalLayout.addWidget(QLabel("startPos"))
        self.verticalLayout.addWidget(self.position)
        self.verticalLayout.addWidget(QLabel("startDir"))
        self.verticalLayout.addWidget(self.rotation)
        self.verticalLayout.addWidget(self.button_savetext)
        self.setWindowTitle("Edit startPos/Dir")

    def closeEvent(self, event):
        self.closing.emit()

    def get_pos_dir(self):
        pos = self.position.text().strip()
        direction = float(self.rotation.text().strip())

        if "," in pos:
            pos = [float(x.strip()) for x in pos.split(",")]
        else:
            pos = [float(x.strip()) for x in pos.split(" ")]

        assert len(pos) == 3

        return pos, direction
