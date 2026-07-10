import json

# TO INPUT SETTINGS RUN MAIN.PY OR GO TO JSON_FILES/SETTINGS.JSON
# TO INPUT SETTINGS RUN MAIN.PY OR GO TO JSON_FILES/SETTINGS.JSON
# TO INPUT SETTINGS RUN MAIN.PY OR GO TO JSON_FILES/SETTINGS.JSON
# TO INPUT SETTINGS RUN MAIN.PY OR GO TO JSON_FILES/SETTINGS.JSON

with open("json_files/settings.json", "r", encoding="utf-8") as f:
    data = json.load(f)

ping: int = int(data["ping"])
station_yaw: float = data["station_yaw"]
bed_spawn: str = data["bed_spawn"]
server_number: str = data["server_number"]

iguanadon: str = data["iguanadon"]
berry_station: str = data["berry_station"]
berry_type: str = data["berry_type"]
external_berry: bool = data["external_berry"]
singleplayer: bool = data["singleplayer"]
iguanadon_seed_throw_amount: int = int(data.get("iguanadon_seed_throw_amount", 18))
time_to_reberry: int = int(data.get("time_to_reberry", 30))
gacha_feed_delay: int = int(data.get("gacha_feed_delay", 6600))
allow_focus_ark_window: bool = data.get("allow_focus_ark_window", True)
focus_ark_window_interval: float = float(data.get("focus_ark_window_interval", 5.0))
helper_inactive_opacity: float = max(
    0.1, min(1.0, float(data.get("helper_inactive_opacity", 0.3)))
)

# -=-=-= OTHER RUNTIME
station_pushout_yaw: float | None = None
wait_structure_load: float = 30
wait_reconnect: float = 60


if __name__ == "__main__":
    pass
