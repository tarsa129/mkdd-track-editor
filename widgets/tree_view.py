from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem
from lib.libbol import BOL, get_full_name
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QAction, QMenu


class BolHeader(QTreeWidgetItem):
    def __init__(self):
        super().__init__()
        self.setText(0, "Track Settings")


class ObjectGroup(QTreeWidgetItem):
    def __init__(self, name, parent=None, bound_to=None):
        if parent is None:
            super().__init__()
        else:
            super().__init__(parent)
        self.setText(0, name)
        self.bound_to = bound_to

    def remove_children(self):
        self.takeChildren()


class ObjectGroupObjects(ObjectGroup):
    def sort(self):
        """items = []
        for i in range(self.childCount()):
            items.append(self.takeChild(0))

        items.sort(key=lambda x: x.bound_to.objectid)

        for item in items:
            self.addChild(item)"""
        self.sortChildren(0, 0)


# Groups
class EnemyPointGroup(ObjectGroup):
    def __init__(self, parent, bound_to):
        super().__init__("Enemy Path", parent=parent, bound_to=bound_to)
        self.update_name()

    def update_name(self):
        index = self.parent().indexOfChild(self)
        if self.bound_to.points:
            link_start = self.bound_to.points[0].link
            link_end = self.bound_to.points[-1].link
        else:
            link_start = link_end = '?'
        self.setText(
            0,
            "Enemy Path {0} (ID: {1}, link: {2}->{3})".format(index,
                                                                     self.bound_to.id,
                                                                     link_start,
                                                                     link_end))


class CheckpointGroup(ObjectGroup):
    def __init__(self, parent, bound_to):
        super().__init__("Checkpoint Group", parent=parent, bound_to=bound_to)
        self.update_name()

    def update_name(self):
        index = self.parent().indexOfChild(self)
        self.setText(0, "Checkpoint Group {0}".format(index))


class ObjectPointGroup(ObjectGroup):
    def __init__(self, parent, bound_to):
        super().__init__("Route", parent=parent, bound_to=bound_to)
        self.update_name()

    def update_name(self):
        index = self.parent().indexOfChild(self)
        self.setText(0, "Route {0}".format(index))


# Entries in groups or entries without groups
class NamedItem(QTreeWidgetItem):
    def __init__(self, parent, name, bound_to, index=None):
        super().__init__(parent)
        self.setText(0, name)
        self.bound_to = bound_to
        self.index = index
        self.update_name()

    def update_name(self):
        pass


class EnemyRoutePoint(NamedItem):
    def update_name(self):
        group_item = self.parent()
        group = group_item.bound_to
        offset = 0
        groups_item = group_item.parent()

        for i in range(groups_item.childCount()):
            other_group_item = groups_item.child(i)
            if other_group_item == group_item:
                break
            else:
                #print("Hmmm,", other_group_item.text(0), len(other_group_item.bound_to.points), offset)
                group_object = other_group_item.bound_to
                offset += len(group_object.points)


        index = group.points.index(self.bound_to)
        point = group.points[index]

        if point.link == -1:
            self.setText(0, "Enemy Point {0} (pos={1})".format(index + offset, index))
        else:
            self.setText(
                0,
                "Enemy Point {0} (pos={1}, link={2})".format(index + offset,
                                                                   index,
                                                                   point.link))


class Checkpoint(NamedItem):
    def update_name(self):
        offset = 0
        group_item = self.parent()
        groups_item = group_item.parent()
        for i in range(groups_item.childCount()):
            other_group_item = groups_item.child(i)
            if other_group_item == group_item:
                break
            else:
                print("Hmmm,",other_group_item.text(0), len(other_group_item.bound_to.points), offset)
                group_object = other_group_item.bound_to
                offset += len(group_object.points)

        group = group_item.bound_to

        index = group.points.index(self.bound_to)

        self.setText(0, "Checkpoint {0} (pos={1})".format(index+offset, index))


class ObjectRoutePoint(NamedItem):
    def update_name(self):
        group_item = self.parent()
        group = group_item.bound_to

        index = group.points.index(self.bound_to)

        self.setText(0, "Route Point {0}".format(index))


class ObjectEntry(NamedItem):
    def __init__(self, parent, name, bound_to):
        super().__init__(parent, name, bound_to)
        bound_to.widget = self

    def update_name(self):
        self.setText(0, get_full_name(self.bound_to.objectid))

    def __lt__(self, other):
        return self.bound_to.objectid < other.bound_to.objectid


class KartpointEntry(NamedItem):
    def update_name(self):
        playerid = self.bound_to.playerid
        if playerid == 0xFF:
            result = "All"
        else:
            result = "ID:{0}".format(playerid)
        self.setText(0, "Kart Start Point {0}".format(result))


class AreaEntry(NamedItem):
    def update_name(self):
        self.setText(0, "Area (Type: {0})".format(self.bound_to.area_type))


class CameraEntry(NamedItem):
    def update_name(self):
        self.setText(0, "Camera {0} (Type: {1})".format(self.index, self.bound_to.camtype))


class RespawnEntry(NamedItem):
    def update_name(self):
        for i in range(self.parent().childCount()):
            if self == self.parent().child(i):
                self.setText(0, "Respawn Point {0} (ID: {1})".format(i, self.bound_to.respawn_id))
                break


class LightParamEntry(NamedItem):
    def update_name(self):
        self.setText(0, "LightParam {0}".format(self.index))


class MGEntry(NamedItem):
    def update_name(self):
        self.setText(0, "MG")


class LevelDataTreeView(QTreeWidget):
    select_all = pyqtSignal(ObjectGroup)
    reverse = pyqtSignal(ObjectGroup)
    duplicate = pyqtSignal(ObjectGroup)
    split = pyqtSignal(EnemyPointGroup, EnemyRoutePoint)
    split_checkpoint = pyqtSignal(CheckpointGroup, Checkpoint)

    def __init__(self, *args, **kwargs):
        super().__init__(*args)

        self.resize(200, self.height())
        self.setColumnCount(1)
        self.setHeaderLabel("Track Data Entries")

        self.bolheader = BolHeader()
        self.addTopLevelItem(self.bolheader)

        self.enemyroutes = self._add_group("Enemy Paths")
        self.checkpointgroups = self._add_group("Checkpoint Groups")
        self.routes = self._add_group("Routes")
        self.objects = self._add_group("Objects", ObjectGroupObjects)
        self.kartpoints = self._add_group("Kart Start Points")
        self.areas = self._add_group("Areas")
        self.cameras = self._add_group("Cameras")
        self.respawnpoints = self._add_group("Respawn Points")
        self.lightparams = self._add_group("Light Params")
        self.mgentries = self._add_group("Minigame Params")

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.run_context_menu)

    def run_context_menu(self, pos):
        item = self.itemAt(pos)

        if isinstance(item, (EnemyRoutePoint, )):
            context_menu = QMenu(self)
            split_action = QAction("Split Group At", self)

            def emit_current_split():
                item = self.itemAt(pos)
                group_item = item.parent()
                self.split.emit(group_item, item)

            split_action.triggered.connect(emit_current_split)

            context_menu.addAction(split_action)
            context_menu.exec(self.mapToGlobal(pos))
            context_menu.destroy()
            del context_menu
        elif isinstance(item, (Checkpoint, )):
            context_menu = QMenu(self)
            split_action = QAction("Split Group At", self)

            def emit_current_split():
                item = self.itemAt(pos)
                group_item = item.parent()
                self.split_checkpoint.emit(group_item, item)

            split_action.triggered.connect(emit_current_split)

            context_menu.addAction(split_action)
            context_menu.exec(self.mapToGlobal(pos))
            context_menu.destroy()
            del context_menu
        elif isinstance(item, (EnemyPointGroup, ObjectPointGroup, CheckpointGroup)):
            context_menu = QMenu(self)
            select_all_action = QAction("Select All", self)
            reverse_action = QAction("Reverse", self)

            def emit_current_selectall():
                item = self.itemAt(pos)
                self.select_all.emit(item)

            def emit_current_reverse():
                item = self.itemAt(pos)
                self.reverse.emit(item)



            select_all_action.triggered.connect(emit_current_selectall)
            reverse_action.triggered.connect(emit_current_reverse)

            context_menu.addAction(select_all_action)
            context_menu.addAction(reverse_action)

            if isinstance(item, EnemyPointGroup):
                def emit_current_duplicate():
                    item = self.itemAt(pos)
                    self.duplicate.emit(item)

                duplicate_action = QAction("Duplicate", self)
                duplicate_action.triggered.connect(emit_current_duplicate)
                context_menu.addAction(duplicate_action)

            context_menu.exec(self.mapToGlobal(pos))
            context_menu.destroy()
            del context_menu

    def _add_group(self, name, customgroup=None):
        if customgroup is None:
            group = ObjectGroup(name)
        else:
            group = customgroup(name)
        self.addTopLevelItem(group)
        return group

    def reset(self):
        self.enemyroutes.remove_children()
        self.checkpointgroups.remove_children()
        self.routes.remove_children()
        self.objects.remove_children()
        self.kartpoints.remove_children()
        self.areas.remove_children()
        self.cameras.remove_children()
        self.respawnpoints.remove_children()
        self.lightparams.remove_children()
        self.mgentries.remove_children()

    def set_objects(self, boldata: BOL):
        self.reset()

        for group in boldata.enemypointgroups.groups:
            group_item = EnemyPointGroup(self.enemyroutes, group)

            for point in group.points:
                point_item = EnemyRoutePoint(group_item, "Enemy Route Point", point)

        for group in boldata.checkpoints.groups:
            group_item = CheckpointGroup(self.checkpointgroups, group)

            for point in group.points:
                point_item = Checkpoint(group_item, "Checkpoint", point)

        for route in boldata.routes:
            route_item = ObjectPointGroup(self.routes, route)

            for point in route.points:
                point_item = ObjectRoutePoint(route_item, "Route Point", point)

        for object in boldata.objects.objects:
            object_item = ObjectEntry(self.objects, "Object", object)

        self.sort_objects()

        for kartpoint in boldata.kartpoints.positions:
            item = KartpointEntry(self.kartpoints, "Kartpoint", kartpoint)

        for area in boldata.areas.areas:
            item = AreaEntry(self.areas, "Area", area)

        for respawn in boldata.respawnpoints:
            item = RespawnEntry(self.respawnpoints, "Respawn", respawn)

        for i, camera in enumerate(boldata.cameras):
            item = CameraEntry(self.cameras, "Camera", camera, i)

        for i, lightparam in enumerate(boldata.lightparams):
            item = LightParamEntry(self.lightparams, "LightParam", lightparam, i)

        for mg in boldata.mgentries:
            item = MGEntry(self.mgentries, "MG", mg)

    def sort_objects(self):
        self.objects.sort()
        """items = []
        for i in range(self.objects.childCount()):
            items.append(self.objects.takeChild(0))

        items.sort(key=lambda x: x.bound_to.objectid)

        for item in items:
            self.objects.addChild(item)"""