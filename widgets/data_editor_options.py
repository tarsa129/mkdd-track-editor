from collections import OrderedDict

ENPT_Setting1 = OrderedDict()
ENPT_Setting1["Default"] = 0
ENPT_Setting1["Only enter with offroad cutting item"] = 1
ENPT_Setting1["Use item"] = 2
ENPT_Setting1["Wheelie"] = 3
ENPT_Setting1["End Wheelie"] = 4
ENPT_Setting1["Unknown (5)"] = 5

ENPT_Setting2 = OrderedDict()
ENPT_Setting2["Default"] = 0
ENPT_Setting2["End Drift"] = 1
ENPT_Setting2["Forbidden drift"] = 2
ENPT_Setting2["Force Drift"] = 3

ITPT_Setting1 = OrderedDict()
ITPT_Setting1["Over Abyss"] = 0
ITPT_Setting1["Default"] = 1
ITPT_Setting1["Follow Exact"] = 2
ITPT_Setting1["Over Bouncy Mushrooms"] = 3

POTI_Setting1 = OrderedDict()
POTI_Setting1["Sharp motion"] = 0
POTI_Setting1["Smooth motion"] = 1

POTI_Setting2 = OrderedDict()
POTI_Setting2["Cyclic motion"] = 0
POTI_Setting2["Back and forth motion"] = 1

POLE_POSITIONS = OrderedDict()
POLE_POSITIONS["Left"] = 0
POLE_POSITIONS["Right"] = 1

START_SQUEEZE = OrderedDict()
START_SQUEEZE["Normal"] = 0
START_SQUEEZE["Narrow"] = 1

AREA_Type = OrderedDict()
AREA_Type["Camera"] = 0
AREA_Type["Environment Effect"] = 1
AREA_Type["BFG Swapper"] = 2
AREA_Type["Moving Road"] = 3
AREA_Type["Destination Point"] = 4
AREA_Type["Minimap Control"] = 5
AREA_Type["BBLM Swapper"] = 6
AREA_Type["Flying Boos"] = 7
AREA_Type["Object Grouper"] = 8
AREA_Type["Group Unloading"] = 9
AREA_Type["Fall Boundary"] = 10
AREA_Type["INVALID"] = 11

AREA_TYPES = [ "Camera (don't use aaaa)", "Environment Effect","BFG Swapper", "Moving Road", "Destination Point" , "Minimap Control",
               "BBLM Swapper", "Flying Boos", "Object Grouper", "Group Unloading", "Fall Boundary"]

AREA_Shape = OrderedDict()
AREA_Shape["Box"] = 0
AREA_Shape["Cylinder"] = 1

CAME_Type = OrderedDict()
CAME_Type["Goal"] = 0
CAME_Type["FixSearch (Replay)"] = 1
CAME_Type["PathSearch (Replay)"] = 2
CAME_Type["KartFollow (Replay)"] = 3
CAME_Type["KartPathFollow (Replay/Opening)"] = 4
CAME_Type["OP_FixMoveAt (Opening)"] = 5
CAME_Type["OP_PathMoveAt (Replay)"] = 6
CAME_Type["MiniGame (Unused)"] = 7
CAME_Type["MissionSuccess (Unused)"] = 8
CAME_Type["MSPT"] = 9
CAME_Type["INVALID"] = 10

CAME_TYPES = ["Goal", "FixSearch (R)", "PathSearch (R)", "KartFollow (R)", "KartPathFollow (R/O)",
                "OP_FixMoveAt(O)", "OP_PathMoveAt (R)", "MiniGame", "MissionSuccess", "MSPT"]

routed_cameras = [2, 5, 6]

CNPT_ShootEffect = OrderedDict()
CNPT_ShootEffect["Straight"] =  0
CNPT_ShootEffect["Curved"] =  1
CNPT_ShootEffect["Curved and Slow"] =  2