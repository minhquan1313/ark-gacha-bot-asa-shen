import json 

#TO INPUT SETTINGS RUN MAIN.PY OR GO TO JSON_FILES/SETTINGS.JSON
#TO INPUT SETTINGS RUN MAIN.PY OR GO TO JSON_FILES/SETTINGS.JSON
#TO INPUT SETTINGS RUN MAIN.PY OR GO TO JSON_FILES/SETTINGS.JSON
#TO INPUT SETTINGS RUN MAIN.PY OR GO TO JSON_FILES/SETTINGS.JSON

with open("json_files/settings.json", "r", encoding='utf-8') as f:
    data = json.load(f)

screen_resolution: str = data["screen_resolution"] # No longer in use. Just here cause people are thoughtless.
base_path: str = data["base_path"] # No longer in use. Just here cause people are thoughtless.
lag_offset: float = data["lag_offset"]
iguanadon: str = data["iguanadon"]
drop_off: str = data["drop_off"]
bed_spawn: str = data["bed_spawn"]
berry_station: str = data["berry_station"]
grindables: str = data["grindables"]
berry_type: str = data["berry_type"]
station_yaw: float = data["station_yaw"]
render_pushout: float = data["render_pushout"]
external_berry: bool = data["external_berry"]
height_ele: int = data["height_ele"]
height_grind: int = data["height_grind"]
singleplayer: bool = data["singleplayer"]
server_number: str = data["server_number"]
crafting: bool = data["crafting"]
seeds_230: bool = data["seeds_230"]
side_crop_plot: bool = data["side_crop_plot"]
y_trap_bot: bool = data["y_trap_bot"]



if __name__ =="__main__":
    pass