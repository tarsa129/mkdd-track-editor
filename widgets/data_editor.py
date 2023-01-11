import os
import json

from PyQt5.QtWidgets import QSizePolicy, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QCheckBox, QLineEdit, QComboBox, QSizePolicy, QColorDialog, QPushButton
from PyQt5.QtGui import QIntValidator, QDoubleValidator, QValidator, QColor
from math import inf
from lib.libkmp import (EnemyPoint, EnemyPointGroup, CheckpointGroup, Checkpoint, Route, RoutePoint, ItemPoint, ItemPointGroup,
                        MapObject, KartStartPoint, KartStartPoints, Area, Camera, Cameras, KMP, JugemPoint, MapObject,
                        CannonPoint, MissionPoint, OBJECTNAMES, REVERSEOBJECTNAMES,
                         Rotation)
from lib.vectors import Vector3
from PyQt5.QtCore import pyqtSignal
from widgets.data_editor_options import *

#test comment

def load_route_info(objectname):
    return None
    """
    try:
        with open(os.path.join("object_parameters", objectname+".json"), "r") as f:
            data = json.load(f)
            if "Route Info" in data.keys():
            
                return data["Route Info"]
            else:
                return None
    except Exception as err:
        print(err, "Make Route Info not found")
        return None
    """
def load_default_info(objectname):
    try:
        with open(os.path.join("object_parameters", objectname+".json"), "r") as f:
            data = json.load(f)
            if "Default Values" in data.keys():
                return data["Default Values"]
            else:
                return None
    except Exception as err:
        print(err, "Default Values not found")
        return None

def load_parameter_names(objectname):

    path = os.path.join("object_parameters", objectname+".json")
    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
            parameter_names = data["Object Parameters"]
            assets = data["Assets"]
            if len(parameter_names) != 8:
                raise RuntimeError("Not enough or too many parameters: {0} (should be 8)".format(len(parameter_names)))
            
            route_info = data["Route Info"]
            
            return parameter_names, assets, route_info
    else:
        return None, None, None

class PythonIntValidator(QValidator):
    def __init__(self, min, max, parent):
        super().__init__(parent)
        self.min = min
        self.max = max

    def validate(self, p_str, p_int):
        if p_str == "" or p_str == "-":
            return QValidator.Intermediate, p_str, p_int

        try:
            result = int(p_str)
        except:
            return QValidator.Invalid, p_str, p_int

        if self.min <= result <= self.max:
            return QValidator.Acceptable, p_str, p_int
        else:
            return QValidator.Invalid, p_str, p_int

    def fixup(self, s):
        pass


class DataEditor(QWidget):
    emit_3d_update = pyqtSignal()
    

    def __init__(self, parent, bound_to):
        super().__init__(parent)

        self.bound_to = bound_to
        self.vbox = QVBoxLayout(self)
        self.vbox.setContentsMargins(0, 0, 0, 0)
        self.vbox.setSpacing(3)

        self.setup_widgets()

    def catch_text_update(self):
        self.emit_3d_update.emit()

    def setup_widgets(self):
        pass

    def update_data(self):
        pass

    def create_label(self, text):
        label = QLabel(self)
        label.setText(text)
        return label

    def create_button(self, text):
        button = QPushButton(self)
        button.setText(text)
        return button

    def add_label(self, text):
        label = self.create_label(text)
        self.vbox.addWidget(label)
        return label

    def create_labeled_widget(self, parent, text, widget):
        layout = QHBoxLayout()
        layout.setSpacing(5)
        label = self.create_label(text)
        label.setText(text)
        layout.addWidget(label)
        layout.addWidget(widget)
        return layout

    def create_labeled_widget_ret_both(self, parent, text, widget):
        layout = QHBoxLayout()
        layout.setSpacing(5)
        label = self.create_label(text)
        label.setText(text)
        layout.addWidget(label)
        layout.addWidget(widget)
        return layout, label

    def create_labeled_widgets(self, parent, text, widgetlist):
        layout = QHBoxLayout()
        layout.setSpacing(5)
        label = self.create_label(text)
        label.setText(text)
        layout.addWidget(label)
        if len(widgetlist) > 1:
            child_layout = QHBoxLayout()
            child_layout.setSpacing(1)
            child_layout.setContentsMargins(0, 0, 0, 0)
            for widget in widgetlist:
                child_layout.addWidget(widget)
            layout.addLayout(child_layout)
        elif widgetlist:
            layout.addWidget(widgetlist[0])
        return layout


    def create_clickable_widgets(self, parent, text, widgetlist):
        layout = QHBoxLayout()
        label = self.create_button(text)
        layout.addWidget(label)
        for widget in widgetlist:
            layout.addWidget(widget)
        return layout


    def add_checkbox(self, text, attribute, off_value, on_value):
        checkbox = QCheckBox(self)
        layout = self.create_labeled_widget(self, text, checkbox)

        def checked(state):
            if state == 0:
                setattr(self.bound_to, attribute, off_value)
            else:
                setattr(self.bound_to, attribute, on_value)

        checkbox.stateChanged.connect(checked)
        self.vbox.addLayout(layout)

        return checkbox

    def add_integer_input(self, text, attribute, min_val, max_val):
        line_edit = QLineEdit(self)
        layout = self.create_labeled_widget(self, text, line_edit)

        line_edit.setValidator(PythonIntValidator(min_val, max_val, line_edit))

        def input_edited():
            #print("Hmmmm")
            text = line_edit.text()
            #print("input:", text)

            setattr(self.bound_to, attribute, int(text))

        line_edit.editingFinished.connect(input_edited)

        self.vbox.addLayout(layout)
        #print("created for", text, attribute)
        return line_edit

    def add_integer_input_hideable(self, text, attribute, min_val, max_val):
        line_edit = QLineEdit(self)
        layout, label = self.create_labeled_widget_ret_both(self, text, line_edit)

        line_edit.setValidator(PythonIntValidator(min_val, max_val, line_edit))

        def input_edited():
            #print("Hmmmm")
            text = line_edit.text()
            #print("input:", text)

            setattr(self.bound_to, attribute, int(text))

        line_edit.editingFinished.connect(input_edited)

        self.vbox.addLayout(layout)
        #print("created for", text, attribute)
        return line_edit, label

    def add_integer_input_index(self, text, attribute, index, min_val, max_val):
        line_edit = QLineEdit(self)
        layout = self.create_labeled_widget(self, text, line_edit)

        line_edit.setValidator(QIntValidator(min_val, max_val, self))

        def input_edited():
            text = line_edit.text()
            #print("input:", text)
            mainattr = getattr(self.bound_to, attribute)
            mainattr[index] = int(text)

        line_edit.editingFinished.connect(input_edited)
        label = layout.itemAt(0).widget()
        self.vbox.addLayout(layout)

        return label, line_edit

    def add_decimal_input(self, text, attribute, min_val, max_val):
        line_edit = QLineEdit(self)
        layout = self.create_labeled_widget(self, text, line_edit)

        line_edit.setValidator(QDoubleValidator(min_val, max_val, 6, self))

        def input_edited():
            text = line_edit.text()
            #print("input:", text)
            self.catch_text_update()
            setattr(self.bound_to, attribute, float(text))

        line_edit.editingFinished.connect(input_edited)

        self.vbox.addLayout(layout)

        return line_edit

    def add_text_input(self, text, attribute, maxlength):
        line_edit = QLineEdit(self)
        layout = self.create_labeled_widget(self, text, line_edit)

        line_edit.setMaxLength(maxlength)

        def input_edited():
            text = line_edit.text()
            text = text.rjust(maxlength)
            setattr(self.bound_to, attribute, text)

        line_edit.editingFinished.connect(input_edited)
        self.vbox.addLayout(layout)

        return line_edit

    def add_text_input_return_both(self, text, attribute, maxlength):
        line_edit = QLineEdit(self)
        layout = self.create_labeled_widget(self, text, line_edit)

        line_edit.setMaxLength(maxlength)

        def input_edited():
            text = line_edit.text()
            text = text.rjust(maxlength)
            setattr(self.bound_to, attribute, text)

        line_edit.editingFinished.connect(input_edited)
        self.vbox.addLayout(layout)

        return line_edit, layout.itemAt(0)

    def add_dropdown_input(self, text, attribute, keyval_dict):
        combobox = QComboBox(self)
        for val in keyval_dict:
            combobox.addItem(val)

        layout = self.create_labeled_widget(self, text, combobox)

        def item_selected(item):
            val = keyval_dict[item]
            #print("selected", item)
            setattr(self.bound_to, attribute, val)

        combobox.currentTextChanged.connect(item_selected)
        self.vbox.addLayout(layout)

        return combobox

    def add_multiple_integer_input(self, text, attribute, subattributes, min_val, max_val):
        line_edits = []
        for subattr in subattributes:
            line_edit = QLineEdit(self)

            if max_val <= MAX_UNSIGNED_BYTE:
                line_edit.setMaximumWidth(90)

            line_edit.setValidator(QIntValidator(min_val, max_val, self))

            input_edited = create_setter(line_edit, self.bound_to, attribute, subattr, self.catch_text_update, isFloat=False)

            line_edit.editingFinished.connect(input_edited)
            line_edits.append(line_edit)

        layout = self.create_labeled_widgets(self, text, line_edits)
        self.vbox.addLayout(layout)


        return line_edits

    def add_multiple_decimal_input(self, text, attribute, subattributes, min_val, max_val):
        line_edits = []
        for subattr in subattributes:
            line_edit = QLineEdit(self)

            line_edit.setValidator(QDoubleValidator(min_val, max_val, 6, self))

            input_edited = create_setter(line_edit, self.bound_to, attribute, subattr, self.catch_text_update, isFloat=True)
            line_edit.editingFinished.connect(input_edited)
            line_edits.append(line_edit)

        layout = self.create_labeled_widgets(self, text, line_edits)
        self.vbox.addLayout(layout)

        return line_edits

    def add_multiple_integer_input_list(self, text, attribute, min_val, max_val):
        line_edits = []
        fieldlist = getattr(self.bound_to, attribute)
        for i in range(len(fieldlist)):
            line_edit = QLineEdit(self)
            line_edit.setMaximumWidth(30)

            line_edit.setValidator(QIntValidator(min_val, max_val, self))

            input_edited = create_setter_list(line_edit, self.bound_to, attribute, i)
            line_edit.editingFinished.connect(input_edited)
            line_edits.append(line_edit)

        layout = self.create_labeled_widgets(self, text, line_edits)
        self.vbox.addLayout(layout)

        return line_edits

    def add_color_input(self, text, attribute, subattributes, min_val, max_val):
        line_edits = []
        for subattr in subattributes:
            line_edit = QLineEdit(self)

            if max_val <= MAX_UNSIGNED_BYTE:
                line_edit.setMaximumWidth(90)

            line_edit.setValidator(QIntValidator(min_val, max_val, self))

            input_edited = create_setter(line_edit, self.bound_to, attribute, subattr, self.catch_text_update, isFloat=False)

            line_edit.editingFinished.connect(input_edited)
            line_edits.append(line_edit)

        layout = self.create_clickable_widgets(self, text, line_edits)
        self.vbox.addLayout(layout)

        return layout.itemAt(0).widget(), line_edits

    def update_rotation(self, xang, yang, zang):
        rotation = self.bound_to.rotation
        euler_angs = rotation.get_euler()

        """

        x, y, z = xang.text(), yang.text(), zang.text()
        x_ang = float( x ) if x.replace('.','',1).isdigit() else 0
        y_ang = float( y ) if y.replace('.','',1).isdigit() else 0
        z_ang = float( y ) if z.replace('.','',1).isdigit() else 0
        """
        
        xang.setText(str(round(euler_angs[0], 4)))
        yang.setText(str(round(euler_angs[1], 4)))
        zang.setText(str(round(euler_angs[2], 4)))
        
        """
        for attr in ("x", "y", "z"):
            if getattr(forward, attr) == 0.0:
                setattr(forward, attr, 0.0)
        for attr in ("x", "y", "z"):
            if getattr(up, attr) == 0.0:
                setattr(up, attr, 0.0)

        for attr in ("x", "y", "z"):
            if getattr(left, attr) == 0.0:
                setattr(left, attr, 0.0)
        """
        """
        forwardedits[0].setText(str(round(degs[0], 4)))
        forwardedits[1].setText(str(round(degs[1], 4)))
        forwardedits[2].setText(str(round(degs[2], 4)))
        """
        
        """
        
        forwardedits[0].setText(str(round(forward.x, 4)))
        forwardedits[1].setText(str(round(forward.y, 4)))
        forwardedits[2].setText(str(round(forward.z, 4)))
        upedits[0].setText(str(round(up.x, 4)))
        upedits[1].setText(str(round(up.y, 4)))
        upedits[2].setText(str(round(up.z, 4)))

        leftedits[0].setText(str(round(left.x, 4)))
        leftedits[1].setText(str(round(left.y, 4)))
        leftedits[2].setText(str(round(left.z, 4)))
        """
        
        #self.bound_to.rotation = Rotation.from_euler(Vector3(x_ang, y_ang, z_ang))
        self.catch_text_update()

    def add_rotation_input(self):
        rotation = self.bound_to.rotation

        
        angle_edits = [] #these are the checkboxes
        for attr in ("x", "y", "z"):
            line_edit = QLineEdit(self)
            validator = QDoubleValidator(-360.0, 360.0, 9999, self)
            validator.setNotation(QDoubleValidator.StandardNotation)
            line_edit.setValidator(validator)

            angle_edits.append(line_edit)
        


        def change_angle():
            newup = Vector3(*[float(v.text()) for v in angle_edits])

            self.bound_to.rotation = Rotation.from_euler(newup)
           
            self.update_rotation(*angle_edits)
            
        for edit in angle_edits:
            edit.editingFinished.connect(change_angle)
       
       
        
       
        layout = self.create_labeled_widgets(self, "Angles", angle_edits)
        
        
        
        self.vbox.addLayout(layout)

        #return forward_edits, up_edits, left_edits
        return angle_edits
    
    def set_value(self, field, val):
        field.setText(str(val))

    def update_name(self):
        if hasattr(self.bound_to, "widget"):
            if self.bound_to.widget is None:
                return
            self.bound_to.widget.update_name()
            if hasattr(self.bound_to.widget, "parent") and self.bound_to.widget.parent() is not None:
                self.bound_to.widget.parent().sort()
            self.bound_to.widget.setSelected(True)
        if isinstance(self.bound_to, MapObject):
            self.bound_to.set_route_info()


def create_setter_list(lineedit, bound_to, attribute, index):
    def input_edited():
        text = lineedit.text()
        mainattr = getattr(bound_to, attribute)
        mainattr[index] = int(text)

    return input_edited


def create_setter(lineedit, bound_to, attribute, subattr, update3dview, isFloat):
    if isFloat:
        def input_edited():
            text = lineedit.text()
            mainattr = getattr(bound_to, attribute)

            setattr(mainattr, subattr, float(text))
            update3dview()
        return input_edited
    else:
        def input_edited():
            text = lineedit.text()
            mainattr = getattr(bound_to, attribute)

            setattr(mainattr, subattr, int(text))
            update3dview()
        return input_edited

MIN_SIGNED_BYTE = -128
MAX_SIGNED_BYTE = 127
MIN_SIGNED_SHORT = -2**15
MAX_SIGNED_SHORT = 2**15 - 1
MIN_SIGNED_INT = -2**31
MAX_SIGNED_INT = 2**31 - 1

MIN_UNSIGNED_BYTE = MIN_UNSIGNED_SHORT = MIN_UNSIGNED_INT = 0
MAX_UNSIGNED_BYTE = 255
MAX_UNSIGNED_SHORT = 2**16 - 1
MAX_UNSIGNED_INT = 2**32 - 1


def choose_data_editor(obj):
    if isinstance(obj, EnemyPoint):
        return EnemyPointEdit
    elif isinstance(obj, EnemyPointGroup):
        return EnemyPointGroupEdit
    elif isinstance(obj, ItemPoint):
        return ItemPointEdit
    elif isinstance(obj, ItemPointGroup):
        return ItemPointGroupEdit
    elif isinstance(obj, CheckpointGroup):
        return CheckpointGroupEdit
    elif isinstance(obj, MapObject):
        return ObjectEdit
    elif isinstance(obj, Checkpoint):
        return CheckpointEdit
    elif isinstance(obj, Route):
        return ObjectRouteEdit
    elif isinstance(obj, RoutePoint):
        return ObjectRoutePointEdit
    elif isinstance(obj, KMP):
        return KMPEdit
    elif isinstance(obj, KartStartPoint):
        return KartStartPointEdit
    elif isinstance(obj, KartStartPoints):
        return KartStartPointsEdit
    elif isinstance(obj, Area):
        return AreaEdit
    
    elif isinstance(obj, Camera):
        return CameraEdit
    elif isinstance(obj, JugemPoint):
        return RespawnPointEdit
    elif isinstance(obj, CannonPoint):
        return CannonPointEdit
    elif isinstance(obj, MissionPoint):
        return MissionPointEdit

    elif isinstance(obj, Cameras):
        return CamerasEdit

    else:
        return None

class EnemyPointGroupEdit(DataEditor):
    def setup_widgets(self):
        self.groupid = self.add_integer_input("Group ID", "id", MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)

        self.prevgroup = self.add_multiple_integer_input_list("Previous Groups", "prevgroup",
                                                              MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        self.nextgroup = self.add_multiple_integer_input_list("Next Groups", "nextgroup",
                                                              MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)

        self.groupid.setReadOnly(True)
        for widget in self.prevgroup:
            widget.setReadOnly(True)
        for widget in self.nextgroup:
            widget.setReadOnly(True)

    def update_data(self):
        obj : EnemyPointGroup = self.bound_to


        self.groupid.setText(str(self.bound_to.id))
        for i, widget in enumerate(self.prevgroup):
            widget.setText(str(obj.prevgroup[i]))
        for i, widget in enumerate(self.nextgroup):
            widget.setText(str(obj.nextgroup[i]))

class EnemyPointEdit(DataEditor):
    def setup_widgets(self, group_editable=False):
        self.position = self.add_multiple_decimal_input("Position", "position", ["x", "y", "z"],
                                                        -inf, +inf)
        self.scale = self.add_decimal_input("Scale", "scale", -inf, inf)

        self.enemyaction = self.add_dropdown_input("Enemy Action 1", "enemyaction", ENPT_Setting1)
        self.enemyaction2 = self.add_dropdown_input("Enemy Action 2", "enemyaction2", ENPT_Setting2)

        self.unknown = self.add_integer_input("Unknown", "unknown",
                                            MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)
        

        for widget in self.position:
            widget.editingFinished.connect(self.catch_text_update)
        for widget in (self.enemyaction, self.enemyaction2):
            widget.currentIndexChanged.connect(lambda _index: self.catch_text_update())

        self.unknown.editingFinished.connect(self.catch_text_update)

    def update_data(self):
        obj: EnemyPoint = self.bound_to
        self.position[0].setText(str(round(obj.position.x, 3)))
        self.position[1].setText(str(round(obj.position.y, 3)))
        self.position[2].setText(str(round(obj.position.z, 3)))

        self.scale.setText(str(obj.scale))
       
        if obj.enemyaction < len(ENPT_Setting1):
            self.enemyaction.setCurrentIndex(obj.enemyaction)
        else:
            self.enemyaction.setCurrentIndex(-1)
        if obj.enemyaction2 < len(ENPT_Setting2):
            self.enemyaction2.setCurrentIndex(obj.enemyaction2)
        else:
            self.enemyaction2.setCurrentIndex(-1)
        self.unknown.setText(str(obj.unknown))

class ItemPointGroupEdit(DataEditor):
    def setup_widgets(self):
        #self.groupid = self.add_integer_input("Group ID", "id", MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)

        self.prevgroup = self.add_multiple_integer_input_list("Previous Groups", "prevgroup",
                                                              MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        self.nextgroup = self.add_multiple_integer_input_list("Next Groups", "nextgroup",
                                                              MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)

    def update_data(self):
        obj = self.bound_to
        #self.groupid.setText(str(self.bound_to.id))

        for i, widget in enumerate(self.prevgroup):
            widget.setText(str(obj.prevgroup[i]))
        for i, widget in enumerate(self.nextgroup):
            widget.setText(str(obj.nextgroup[i]))

class ItemPointEdit(DataEditor):
    def setup_widgets(self, group_editable=False):
        self.position = self.add_multiple_decimal_input("Position", "position", ["x", "y", "z"],
                                                        -inf, +inf)
        self.scale = self.add_decimal_input("Bullet Bill Range", "scale", -inf, inf)

        self.setting1 = self.add_dropdown_input("Enemy Action 1", "setting1", ITPT_Setting1)
        self.unknown = self.add_checkbox("Unknown", "unknown", off_value=0, on_value=1)
        self.lowpriority = self.add_checkbox("Low Priority", "lowpriority", off_value=0, on_value=1)
        self.dontdrop = self.add_checkbox("Don't Drop Bill", "dontdrop", off_value=0, on_value=1)


    def update_data(self):
        obj: ItemPoint = self.bound_to
        self.position[0].setText(str(round(obj.position.x, 3)))
        self.position[1].setText(str(round(obj.position.y, 3)))
        self.position[2].setText(str(round(obj.position.z, 3)))
       
        if obj.setting1 < len(ITPT_Setting1):
            self.setting1.setCurrentIndex(obj.setting1)
        else:
            self.setting1.setCurrentIndex(-1)

        self.scale.setText(str(obj.scale))

        self.unknown.setChecked( obj.unknown !=0 )
        self.lowpriority.setChecked( obj.lowpriority !=0 )
        self.dontdrop.setChecked( obj.dontdrop !=0 )

class CheckpointGroupEdit(DataEditor):


    def setup_widgets(self):
        #self.id = self.add_integer_input("Group ID", "id", MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)
        self.prevgroup = self.add_multiple_integer_input_list("Previous Groups", "prevgroup",
                                                              MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
        self.nextgroup = self.add_multiple_integer_input_list("Next Groups", "nextgroup",
                                                              MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)

    def update_data(self):
        obj = self.bound_to
        #self.id.setText(str(obj.id))
        for i, widget in enumerate(self.prevgroup):
            widget.setText(str(obj.prevgroup[i]))
        for i, widget in enumerate(self.nextgroup):
            widget.setText(str(obj.nextgroup[i]))

class CheckpointEdit(DataEditor):
    def setup_widgets(self):
        self.start = self.add_multiple_decimal_input("Start", "start", ["x", "z"],
                                                        -inf, +inf)
        self.end = self.add_multiple_decimal_input("End", "end", ["x", "z"],
                                                     -inf, +inf)

        self.respawn = self.add_integer_input("Respawn", "respawn",
                                           MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)
        self.type = self.add_checkbox("Key CP", "type",
                                      0, 1)                

    def update_data(self):
        obj: Checkpoint = self.bound_to
        
        self.start[0].setText(str(round(obj.start.x, 3)))
        self.start[1].setText(str(round(obj.start.z, 3)))

        self.end[0].setText(str(round(obj.end.x, 3)))
        self.end[1].setText(str(round(obj.end.z, 3)))

        self.respawn.setText(str(obj.respawn))
        self.type.setChecked(obj.type != 0)

class ObjectRouteEdit(DataEditor):
    def setup_widgets(self):
        self.smooth = self.add_dropdown_input("Sharp/Smooth motion", "smooth", POTI_Setting1) 
        self.cyclic = self.add_dropdown_input("Cyclic/Back and forth motion", "cycle", POTI_Setting2) 

    def update_data(self):
        obj: Route = self.bound_to
        self.smooth.setCurrentIndex( min(obj.smooth, 1)) 
        self.cyclic.setCurrentIndex( min(obj.cyclic, 1)) 

class ObjectRoutePointEdit(DataEditor):
    def setup_widgets(self):
        self.position = self.add_multiple_decimal_input("Position", "position", ["x", "y", "z"],
                                                        -inf, +inf)
        self.unk1 = self.add_integer_input("Setting 1", "unk1",
                                              MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)
        self.unk2 = self.add_integer_input("Setting 2", "unk2",
                                              MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)

    def update_data(self):
        obj: RoutePoint = self.bound_to
        self.position[0].setText(str(round(obj.position.x, 3)))
        self.position[1].setText(str(round(obj.position.y, 3)))
        self.position[2].setText(str(round(obj.position.z, 3)))
        self.unk1.setText(str(obj.unk1)) 
        self.unk2.setText(str(obj.unk2)) 

class KMPEdit(DataEditor):
    def setup_widgets(self):

        self.lap_count = self.add_integer_input("Lap Count", "lap_count",
                                        MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)

        self.speed_modifier = self.add_decimal_input("Speed Modifier", "speed_modifier", -inf, +inf)
                                        
        

        self.lens_flare = self.add_checkbox("Enable Lens Flare", "lens_flare",
                                            off_value=0, on_value=1)

        self.flare_colorbutton, self.flare_color = self.add_color_input("Flare Color", "flare_color", ["r", "g", "b"],
                                                           MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)
        self.flare_colorbutton.clicked.connect(lambda: self.open_color_picker_light("flare_color") )  
        self.flare_alpha = self.add_integer_input("Flare Alpha %", "flare_alpha",
                                           MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)

            

       

    def update_data(self):
        obj: KMP = self.bound_to
        #self.roll.setText(str(obj.roll))
        self.lap_count.setText(str(obj.lap_count))
        self.lens_flare.setChecked(obj.lens_flare != 0)
        self.flare_color[0].setText(str(obj.flare_color.r))
        self.flare_color[1].setText(str(obj.flare_color.g))
        self.flare_color[2].setText(str(obj.flare_color.b))
        self.flare_alpha.setText(str(obj.flare_alpha))
        self.speed_modifier.setText(str(obj.speed_modifier))

    def open_color_picker_light(self, attrib): 
        obj = self.bound_to

    
        color_dia = QColorDialog(self)
        #color_dia.setCurrentColor( QColor(curr_color.r, curr_color.g, curr_color.b, curr_color.a) )

        color = color_dia.getColor()
        if color.isValid():
            color_comps = color.getRgbF()
            color_vec = getattr(obj, attrib )
            
            color_vec.r = int(color_comps[0] * 255)
            color_vec.g = int(color_comps[1] * 255)
            color_vec.b = int(color_comps[2] * 255)
            
            self.update_data()

class ObjectEdit(DataEditor):
    emit_route_update = pyqtSignal("PyQt_PyObject", "int", "int")

    #want it so that in the making stage, changing the id changes the defaults
    #once the object has been created fully, then changing the id changes the defaults

    def setup_widgets(self, inthemaking = False):
        self.position = self.add_multiple_decimal_input("Position", "position", ["x", "y", "z"],
                                                        -inf, +inf)
        self.scale = self.add_multiple_decimal_input("Scale", "scale", ["x", "y", "z"],
                                                    -inf, +inf)
        self.rotation = self.add_rotation_input()
        self.objectid = self.add_dropdown_input("Object Type", "objectid", REVERSEOBJECTNAMES)

        self.route, self.route_label = self.add_integer_input_hideable("Object Path ID", "route",
                                             MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)

        self.single = self.add_checkbox("Enable in single player mode", "single", 0, 1)
        self.double = self.add_checkbox("Enable in two player mode", "double", 0, 1)
        self.triple = self.add_checkbox("Enable in three/four player mode", "triple", 0, 1)

        self.userdata = []
        for i in range(8):
            self.userdata.append(
                self.add_integer_input_index("Obj Data {0}".format(i+1), "userdata", i,
                                             MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)
            )

        self.objectid.currentTextChanged.connect(self.update_name)
        self.route.editingFinished.disconnect()
        self.route.editingFinished.connect(self.update_route_used)

        for widget in self.position:
            widget.editingFinished.connect(self.catch_text_update)
        #print(self.objectid.currentText())
        #self.rename_object_parameters(self.objectid.currentText())

        
        self.objectid.currentTextChanged.connect(self.rename_object_parameters)

        if (inthemaking):
            self.set_default_values()

        self.assets = self.add_label("Required Assets: Unknown")
        self.assets.setWordWrap(True)
        hint = self.assets.sizePolicy()
        hint.setVerticalPolicy(QSizePolicy.Minimum)
        self.assets.setSizePolicy(hint)

    def rename_object_parameters(self, current):
        
        parameter_names, assets, route_info = load_parameter_names(current)

        #parameter_names = None
        #assets = []
        
        if parameter_names is None:
            for i in range(8):
                self.userdata[i][0].setText("Obj Data {0}".format(i+1))
                self.userdata[i][0].setVisible(True)
                self.userdata[i][1].setVisible(True)
            self.assets.setText("Required Assets: Unknown")

            self.route.setVisible(True)
            self.route_label.setVisible(True)

        else:
            for i in range(8):
                if parameter_names[i] == "Unused":
                    self.userdata[i][0].setVisible(False)
                    self.userdata[i][1].setVisible(False)
                    if self.bound_to.userdata[i] != 0:
                        Warning("Parameter with index {0} in object {1} is marked as Unused but has value {2}".format(
                            i, current, self.bound_to.userdata[i]
                        ))
                else:
                    self.userdata[i][0].setVisible(True)
                    self.userdata[i][1].setVisible(True)
                    self.userdata[i][0].setText(parameter_names[i])
            if len(assets) == 0:
                self.assets.setText("Required Assets: None")
            else:
                self.assets.setText("Required Assets: {0}".format(", ".join(assets)))

            self.route.setVisible(route_info is not None)
            self.route_label.setVisible(route_info is not None)

            
                
        if hasattr(self, "in_production") and self.in_production:
            self.set_default_values()
    def set_default_values(self):
    
        #assert (1 == 0)
    
        obj: MapObject = self.bound_to
        print("set defaut values", obj)
        
        if obj.objectid not in OBJECTNAMES:
            name = "INVALID"
        else:
            name = OBJECTNAMES[obj.objectid]
        
        if name != "INVALID":
            defaults = load_default_info(name)
            
            
            if defaults is not None:
                defaults = [0 if x is None else x for x in defaults]
                obj.userdata = defaults.copy()
                
                for i in range(8):
                    if defaults[i] is not None:
                        self.userdata[i][1].setText(str(obj.userdata[i]))
            else:
                obj.userdata = [0] * 8
                for i in range(8):
                    self.userdata[i][1].setText("0")
        self.update_data()
    def update_data(self, load_defaults = False):
        obj: MapObject = self.bound_to
        self.position[0].setText(str(round(obj.position.x, 3)))
        self.position[1].setText(str(round(obj.position.y, 3)))
        self.position[2].setText(str(round(obj.position.z, 3)))

        self.scale[0].setText(str(round(obj.scale.x, 3)))
        self.scale[1].setText(str(round(obj.scale.y, 3)))
        self.scale[2].setText(str(round(obj.scale.z, 3)))

        self.update_rotation(*self.rotation)

        if obj.objectid not in OBJECTNAMES:
            name = "INVALID"
        else:
            name = OBJECTNAMES[obj.objectid]
        index = self.objectid.findText(name)
        self.objectid.setCurrentIndex(index)

        self.route.setText(str(obj.route))
       
        self.single.setChecked( obj.single != 0)
        self.double.setChecked( obj.double != 0)
        self.triple.setChecked( obj.triple != 0)
  
        if load_defaults:
            self.in_production = load_defaults
            self.set_default_values()
        else:
            for i in range(8):
                self.userdata[i][1].setText(str(obj.userdata[i]))
    def update_route_used(self):
        #print('update route used', self.bound_to.route)
        #emit signal with old and new route numbers, for easier changing
        self.emit_route_update.emit(self.bound_to, self.bound_to.route, int(self.route.text()) )
        
        #now update the value
        self.bound_to.route = int(self.route.text())
        
        #update the name, may be needed
        self.update_name()

class KartStartPointsEdit(DataEditor):
    def setup_widgets(self):
        self.pole_position = self.add_dropdown_input("Pole Position", "pole_position", POLE_POSITIONS )
        self.start_squeeze = self.add_dropdown_input("Start Distance", "start_squeeze", START_SQUEEZE )

        self.pole_position.currentIndexChanged.connect(self.update_starting_info)
        self.start_squeeze.currentIndexChanged.connect(self.update_starting_info)
    def update_data(self):
        obj: KartStartPoints = self.bound_to
        self.pole_position.setCurrentIndex( min(1, obj.pole_position) )
        self.start_squeeze.setCurrentIndex( min(1, obj.start_squeeze) )

    def update_starting_info(self):
        self.bound_to.pole_position = self.pole_position.currentIndex()
        self.bound_to.start_squeeze = self.start_squeeze.currentIndex()
        
        self.update_name()

    def update_name(self):
        super().update_name()

class KartStartPointEdit(DataEditor):
    def setup_widgets(self):
        self.position = self.add_multiple_decimal_input("Position", "position", ["x", "y", "z"],
                                                        -inf, +inf)
        self.rotation = self.add_rotation_input()
        
        self.playerid = self.add_integer_input("Player ID", "playerid",
                                               MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)
        

    def update_data(self):
        obj: KartStartPoint = self.bound_to
        self.position[0].setText(str(round(obj.position.x, 3)))
        self.position[1].setText(str(round(obj.position.y, 3)))
        self.position[2].setText(str(round(obj.position.z, 3)))

        self.update_rotation(*self.rotation)
        self.playerid.setText(str(obj.playerid))

class AreaEdit(DataEditor):
    emit_camera_update = pyqtSignal("PyQt_PyObject", "int", "int")

    def setup_widgets(self):
        self.position = self.add_multiple_decimal_input("Position", "position", ["x", "y", "z"],
                                                        -inf, +inf)
        self.scale = self.add_multiple_decimal_input("Scale", "scale", ["x", "y", "z"],
                                                     -inf, +inf)
        self.rotation = self.add_rotation_input()

        self.area_type = self.add_dropdown_input("Area Type", "type", AREA_Type)
                                                

        self.shape = self.add_dropdown_input("Shape", "shape", AREA_Shape)

        self.priority = self.add_integer_input("Priority", "priority",
                                           MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)                                           

        self.camera_index, self.camera_index_label = self.add_integer_input_hideable("Camera Index", "camera_index",
                                                   MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)

        self.setting1, self.setting1_label = self.add_integer_input_hideable("Setting 1", "setting1", MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)
        self.setting2, self.setting2_label = self.add_integer_input_hideable("Setting 2", "setting2", MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)
        
        self.routeid, self.routeid_label = self.add_integer_input_hideable("Route ID", "route", MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)
        self.enemypointid, self.enemypointid_label = self.add_integer_input_hideable("Enemy Point ID", "enemypointid", MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)

        self.area_type.currentIndexChanged.connect(self.update_name)
        self.camera_index.editingFinished.disconnect()
        self.camera_index.editingFinished.connect(self.update_camera_used)

    def update_data(self):
        obj: Area = self.bound_to
        self.position[0].setText(str(round(obj.position.x, 3)))
        self.position[1].setText(str(round(obj.position.y, 3)))
        self.position[2].setText(str(round(obj.position.z, 3)))

        self.scale[0].setText(str(round(obj.scale.x, 3)))
        self.scale[1].setText(str(round(obj.scale.y, 3)))
        self.scale[2].setText(str(round(obj.scale.z, 3)))

        self.update_rotation(*self.rotation)

        self.shape.setCurrentIndex( obj.shape )
        self.area_type.setCurrentIndex( obj.type )
        self.camera_index.setText(str(obj.camera_index))
        self.priority.setText(str(obj.priority))
    
        self.setting1.setText(str(obj.setting1))
        self.setting2.setText(str(obj.setting2))
        self.routeid.setText(str(obj.route))
        self.enemypointid.setText(str(obj.enemypointid))
        self.set_settings_visible()

    def set_settings_visible(self):
        obj: Area = self.bound_to
        obj.type = self.area_type.currentIndex()
        self.camera_index.setVisible( obj.type == 0 )
        self.camera_index_label.setVisible( obj.type == 0 )


        setting1_labels = { 2: "BFG Entry", 3: "Acceleration Modifier", 6: "BBLM Entry", 8: "Group ID", 9: "Group ID"  }
        self.setting1.setVisible(obj.type in [2, 3, 6, 8, 9])
        if obj.type in [2, 3, 6, 8, 9]:
            self.setting1_label.setText(setting1_labels[ obj.type ])
        self.setting1_label.setVisible(obj.type in [2, 3, 6, 8, 9])
        

        setting2_labels = { 3: "Moving Water Speed", 6: "Transition Time (frames)"}
        self.setting2.setVisible(obj.type in [3, 6])
        if obj.type in [3, 6]:
            self.setting2_label.setText( setting2_labels[obj.type]   )
        self.setting2_label.setVisible(obj.type in [3, 6])
        

        self.routeid.setVisible(obj.type == 3)
        self.routeid_label.setVisible(obj.type == 3)
        self.enemypointid.setVisible(obj.type == 4)
        self.enemypointid_label.setVisible(obj.type == 4)

    def update_name(self):
        self.set_settings_visible()
        super().update_name()

    def update_camera_used(self):
        #print('update route used', self.bound_to.route)
        #emit signal with old and new route numbers, for easier changing
        self.emit_camera_update.emit(self.bound_to, self.bound_to.camera_index, int(self.camera_index.text()) )
        
        #now update the value
        self.bound_to.camera_index = int(self.camera_index.text())
        
        #update the name, may be needed
        self.update_name()

class CamerasEdit(DataEditor):
    def setup_widgets(self):
        self.startcam = self.add_integer_input("Starting Camera", "startcam", 0, 255)

        self.startcam.editingFinished.connect(self.update_starting_cam)
    def update_data(self):
        obj: Cameras = self.bound_to
        self.startcam.setText( str(obj.startcam) )

    def update_starting_cam(self):
        self.bound_to.startcam = int(self.startcam.text())
        self.update_name()

    def update_name(self):
        super().update_name()

class CameraEdit(DataEditor):
    emit_route_update = pyqtSignal("PyQt_PyObject", "int", "int")

    def setup_widgets(self):
        self.position = self.add_multiple_decimal_input("Position", "position", ["x", "y", "z"],
                                                        -inf, +inf)
        self.rotation = self.add_rotation_input()
        
        self.position2 = self.add_multiple_decimal_input("Start Point", "position2", ["x", "y", "z"],
                                                        -inf, +inf)
        self.position3 = self.add_multiple_decimal_input("End Point", "position3", ["x", "y", "z"],
                                                        -inf, +inf)
        
        self.type = self.add_dropdown_input("Camera Type", "type", CAME_Type)

        self.nextcam = self.add_integer_input("Next Cam", "nextcam",
                                              MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)

        self.shake = self.add_integer_input("Shake", "shake", MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)

        self.route = self.add_integer_input("Object Path ID", "route",
                                            MIN_SIGNED_BYTE, MAX_SIGNED_BYTE)

        self.routespeed = self.add_integer_input("Route Speed", "routespeed", MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)
        self.zoomspeed = self.add_integer_input("Zoom Speed", "zoomspeed", MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)
        self.viewspeed = self.add_integer_input("View Speed", "viewspeed", MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)

        self.fov = self.add_multiple_integer_input("Start/End FOV", "fov", ["start", "end"],
                                                   MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)
        self.camduration = self.add_integer_input("Camera Duration", "camduration",
                                                  MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)

        self.startflag = self.add_integer_input("Start Flag", "startflag", MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)
        self.movieflag = self.add_integer_input("Movie Flag", "movieflag", MIN_UNSIGNED_BYTE, MAX_UNSIGNED_BYTE)

        self.type.currentIndexChanged.connect(self.update_name)
        self.route.editingFinished.disconnect()
        self.route.editingFinished.connect(self.update_route_used)

    def update_data(self):
        obj: Camera = self.bound_to
        self.position[0].setText(str(round(obj.position.x, 3)))
        self.position[1].setText(str(round(obj.position.y, 3)))
        self.position[2].setText(str(round(obj.position.z, 3)))

        self.position2[0].setText(str(round(obj.position2.x, 3)))
        self.position2[1].setText(str(round(obj.position2.y, 3)))
        self.position2[2].setText(str(round(obj.position2.z, 3)))

        self.position3[0].setText(str(round(obj.position3.x, 3)))
        self.position3[1].setText(str(round(obj.position3.y, 3)))
        self.position3[2].setText(str(round(obj.position3.z, 3)))

        self.update_rotation(*self.rotation)

   
        self.type.setCurrentIndex( obj.type )
        self.nextcam.setText(str(obj.nextcam))
        self.shake.setText(str(obj.shake))
        self.route.setText(str(obj.route))
        self.routespeed.setText(str(obj.routespeed))
        self.zoomspeed.setText(str(obj.zoomspeed))
        self.viewspeed.setText(str(obj.viewspeed))
        self.startflag.setText(str(obj.startflag))
        self.movieflag.setText(str(obj.movieflag))

        self.fov[0].setText(str(obj.fov.start))
        self.fov[1].setText(str(obj.fov.end))
        self.camduration.setText(str(obj.camduration))
    

        self.nextcam.setText(str(obj.nextcam))

    def update_route_used(self):
        #print('update route used', self.bound_to.route)
        #emit signal with old and new route numbers, for easier changing
        self.emit_route_update.emit(self.bound_to, self.bound_to.route, int(self.route.text()) )
        
        #now update the value
        self.bound_to.route = int(self.route.text())
        
        #update the name, may be needed
        self.update_name()

class RespawnPointEdit(DataEditor):
    def setup_widgets(self):
        self.position = self.add_multiple_decimal_input("Position", "position", ["x", "y", "z"],
                                                        -inf, +inf)
        self.rotation = self.add_rotation_input()
        
        #self.respawn_id = self.add_integer_input("Respawn ID", "respawn_id", MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)
        self.range = self.add_integer_input("Range", "range",
                                           MIN_SIGNED_SHORT, MAX_SIGNED_SHORT)

    def update_data(self):
        obj: JugemPoint = self.bound_to
        self.position[0].setText(str(round(obj.position.x, 3)))
        self.position[1].setText(str(round(obj.position.y, 3)))
        self.position[2].setText(str(round(obj.position.z, 3)))
        self.update_rotation(*self.rotation)
        self.range.setText(str(obj.range))

class CannonPointEdit(DataEditor):
    def setup_widgets(self):
        self.position = self.add_multiple_decimal_input("Position", "position", ["x", "y", "z"],
                                                        -inf, +inf)
        self.rotation = self.add_rotation_input()
        self.cannon_id = self.add_integer_input("Cannon ID", "id",  MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)
        self.shooteffect = self.add_dropdown_input("Shoot Effect", "shoot_effect", CNPT_ShootEffect)


    def update_data(self):
        obj: CannonPoint = self.bound_to
        self.position[0].setText(str(round(obj.position.x, 3)))
        self.position[1].setText(str(round(obj.position.y, 3)))
        self.position[2].setText(str(round(obj.position.z, 3)))
        self.update_rotation(*self.rotation)
        self.cannon_id.setText(str(obj.id))
        self.shooteffect.setCurrentIndex( obj.shoot_effect )

class MissionPointEdit(DataEditor):
    def setup_widgets(self):
        self.position = self.add_multiple_decimal_input("Position", "position", ["x", "y", "z"],
                                                        -inf, +inf)
        self.rotation = self.add_rotation_input()
        #self.mission_id = self.add_integer_input("Mission Success ID", "mission_id", MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)
        self.unk = self.add_integer_input("Next Enemy Point", "unk",
                                           MIN_UNSIGNED_SHORT, MAX_UNSIGNED_SHORT)

    def update_data(self):
        obj: MissionPoint = self.bound_to
        self.position[0].setText(str(round(obj.position.x, 3)))
        self.position[1].setText(str(round(obj.position.y, 3)))
        self.position[2].setText(str(round(obj.position.z, 3)))
        self.update_rotation(*self.rotation)
        #self.mission_id.setText(str(obj.mission_id))
        self.unk.setText(str(obj.unk))
