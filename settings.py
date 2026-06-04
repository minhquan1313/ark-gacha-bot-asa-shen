import json

# TO INPUT SETTINGS RUN MAIN.PY OR GO TO JSON_FILES/SETTINGS.JSON
# TO INPUT SETTINGS RUN MAIN.PY OR GO TO JSON_FILES/SETTINGS.JSON
# TO INPUT SETTINGS RUN MAIN.PY OR GO TO JSON_FILES/SETTINGS.JSON
# TO INPUT SETTINGS RUN MAIN.PY OR GO TO JSON_FILES/SETTINGS.JSON

with open("json_files/settings.json", "r", encoding="utf-8") as f:
    data = json.load(f)

lag_offset: float = data["lag_offset"]
iguanadon: str = data["iguanadon"]
bed_spawn: str = data["bed_spawn"]
berry_station: str = data["berry_station"]
berry_type: str = data["berry_type"]
station_yaw: float = data["station_yaw"]
external_berry: bool = data["external_berry"]
singleplayer: bool = data["singleplayer"]
server_number: str = data["server_number"]
seeds_230: bool = data["seeds_230"]
gacha_feed_delay: int = int(data.get("gacha_feed_delay", 6600))
gacha_230_feed_delay: int = int(data.get("gacha_230_feed_delay", 10700))
side_crop_plot: bool = data["side_crop_plot"]
allow_focus_ark_window: bool = data.get("allow_focus_ark_window", True)
focus_ark_window_interval: float = float(data.get("focus_ark_window_interval", 5.0))
helper_inactive_opacity: float = max(
    0.1, min(1.0, float(data.get("helper_inactive_opacity", 0.3)))
)
dedi_handshake_timeout: int = int(data.get("dedi_handshake_timeout", 30))


if __name__ == "__main__":
    pass
