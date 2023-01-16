import json

class mapobject(object):
    def __init__(self):
        self.id = 0
        self.name = ""
        self.settings = ["Unused"] * 8
        self.route = None
        
        self.assets = [False] * 4
        #brres, effects, collision, brasd
        
        self.description = ""
 

def build_assets_string( bool_array ):
    assets_array = []
    if bool_array[0]:
        assets_array.append(".brres file needed")
    if bool_array[1]:
        assets_array.append(".breff/.breft files needed")
    if bool_array[2]:
        assets_array.append(".kcl files needed")
    if bool_array[3]:
        assets_array.append(".brasd files needed")
        
    return assets_array

with open("objects.txt", "r") as f:
    lines = f.readlines()

with open( "default_settings.json", "r") as f:
    default_settings = json.load(f)



current_object = mapobject()
all_objects = []   

for line in lines:
    if line.startswith("{{"):
        settings = line.split("|")
        current_object.id = int( settings[3] )
        current_object.name = settings[4]
        if "R" in settings[6]:
            current_object.route = 2
            
        if "(" in settings[5]:
            assets_settings = settings[5][ settings[5].index("(") + 1 : settings[5].index(")") + 1 ]
        
            current_object.assets[0] = "B" in assets_settings
            current_object.assets[1] = "E" in assets_settings
            current_object.assets[2] = "K" in assets_settings
            current_object.assets[3] = "D" in assets_settings
        
    elif line.startswith("|s"):
        index = int(line[2])
        line = line.replace("'", "")
        if not ( line[5: ].startswith("&mdash;") ):
            current_object.settings[index - 1] = line[5:-1 ]
    elif line.startswith("|info"):
        info =  line[7: ]
        current_object.description = info[:-1]
    elif line.startswith("}}"):
        all_objects.append(current_object)
        current_object = mapobject()
            
for current_object in all_objects:
    settings = [None] * 8
    if str(current_object.id) in default_settings:
        settings = default_settings[str(current_object.id)]
        if sum(settings) == 0:
            settings = [None] * 8
    object_dictionary = {  
        "Object Parameters" : current_object.settings,
        "Assets" : build_assets_string(current_object.assets),
        "Default Values" : settings,
        "Route Info": current_object.route,
        "Description" : current_object.description
        }

    # Serializing json
    json_object = json.dumps(object_dictionary, indent=4)
    
    # Writing to sample.json
    with open(current_object.name + ".json", "w") as outfile:
        outfile.write(json_object)
