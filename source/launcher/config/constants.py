SETTINGS_FILE = "json_files/settings.json"
GACHA_LOG_FILE = "source/logs/logs.txt"
JOIN_LOG_FILE = "source/join_sim/source/logs/logs.txt"
MAX_LAUNCHER_LOG_LINES = 2000
APP_NAME = "Shen GBot"
APP_TITLE = APP_NAME.upper()
APP_VERSION = "v1.0.0"
SUPPORTED_GAME_RESOLUTIONS = ((1920, 1080),)
GAME_WINDOW_TITLE = "Ark: Survival Ascended ("
BUTTON_TRANSITION_MS = 200
BREAKPOINT_NARROW_WIDTH = 720
PC_MINIMUM_SIZE = (1180, 680)
PHONE_MINIMUM_SIZE = (420, 640)
TITLE_BAR_HEIGHT = 42
WINDOW_RESIZE_BORDER_PX = 8
ENABLE_NATIVE_CUSTOM_CHROME = True
RUNNER_WIDTH = 240
HELPER_WIDTH = 240
HELPER_HEIGHT = 20
MINIMAL_HELPER_RUNNING_WIDTH = 240

COLORS = {
    "bg": "#070A0F",
    "panel": "#0A1019",
    "panel_strong": "#03070C",
    "panel_soft": "#101C2B",
    "cyan": "#00D8FF",
    "blue": "#2F80FF",
    "green": "#6BFF9E",
    "yellow": "#FFD166",
    "red": "#FF4D6D",
    "text": "#F4F8FF",
    "muted": "#8EA3B8",
    "dim": "#5F7285",
    "border": "#16465A",
}

helper_window_opacity = 0.85
UI_COLORS = {
    "panel_bg": "rgba(10, 16, 25, 205)",
    "panel_bg_soft": "rgba(18, 28, 42, 82)",
    "panel_bg_strong": "rgba(3, 7, 12, 215)",
    "field_bg": "rgba(5, 10, 16, 190)",
    "border_soft": "rgba(0, 216, 255, 54)",
    "border_active": "rgba(0, 216, 255, 135)",
    "helper_row_bg": "rgba(18, 28, 42, 115)",
    "helper_details_bg": "rgba(5, 10, 16, 92)",
    "helper_shell_bg": f"rgba(10, 16, 25, {int(helper_window_opacity * 255)})",
}

UI_METRICS = {
    "radius_sm": 6,
    "radius_md": 9,
    "radius_lg": 12,
    "window_radius": 12,
    "control_height": 32,
    "combo_height": 32,
    "switch_height": 32,
    "icon_button_width": 32,
    "helper_expand_height": 26,
    "helper_expand_width": 28,
    "icon_padding": "2px",
    "control_padding": "2px 12px",
    "combo_padding": "2px 30px 2px 12px",
    "split_button_padding": "2px 34px 2px 12px",
    "menu_padding": "4px",
    "menu_item_padding": "8px 18px",
    "chrome_button_padding": "0px",
    "panel_padding": 14,
    "helper_padding": 8,
    "tool_cover_min_height": 190,
    "smooth_scroll_ms": 210,
}

UI_FONTS = {
    "display": "Segoe UI",
    "body": "Segoe UI",
    "mono": "Consolas",
}

FONT_SIZES = {
    "chrome_title": 21,
    "chrome_version": 9,
    "chrome_status": 10,
    "sidebar_brand": 16,
    "nav": 12,
    "panel_title": 12,
    "page_title": 14,
    "welcome_title": 30,
    "section_heading": 16,
    "stat_label": 11,
    "stat_value": 24,
    "footer": 12,
    "console": 11,
    "form": 11,
    "button": 11,
    "dialog_title": 16,
    "dialog_message": 11,
    "step_number": 18,
    "badge": 10,
    "update_icon": 34,
    "about_title": 22,
}

BUTTON_STYLES = {
    "primary": {
        "normal": {"bg": "#0A2431", "fg": COLORS["cyan"], "border": "#00A9C8"},
        "hover": {"bg": "#0E3A4D", "fg": COLORS["text"], "border": COLORS["cyan"]},
        "active": {"bg": "#11536B", "fg": "#FFFFFF", "border": COLORS["cyan"]},
        "disabled": {"bg": "#101820", "fg": COLORS["dim"], "border": "#1D3440"},
    },
    "secondary": {
        "normal": {"bg": "#121C2A", "fg": COLORS["text"], "border": COLORS["border"]},
        "hover": {"bg": "#182B3A", "fg": COLORS["cyan"], "border": "#00A9C8"},
        "active": {"bg": "#20394B", "fg": "#FFFFFF", "border": COLORS["cyan"]},
        "disabled": {"bg": "#101820", "fg": COLORS["dim"], "border": "#1D3440"},
    },
    "danger": {
        "normal": {"bg": "#291018", "fg": COLORS["red"], "border": "#A83A50"},
        "hover": {"bg": "#401321", "fg": "#FFFFFF", "border": COLORS["red"]},
        "active": {"bg": "#5A172B", "fg": "#FFFFFF", "border": COLORS["red"]},
        "disabled": {"bg": "#181014", "fg": COLORS["dim"], "border": "#3A1D26"},
    },
    "nav": {
        "normal": {"bg": "#050A10", "fg": COLORS["text"], "border": "#050A10"},
        "hover": {"bg": "#07131D", "fg": COLORS["cyan"], "border": "#07131D"},
        "active": {"bg": "#0D3449", "fg": COLORS["cyan"], "border": "#0D3449"},
        "disabled": {"bg": "#050A10", "fg": COLORS["dim"], "border": "#050A10"},
    },
    "chrome": {
        "normal": {"bg": "#03070C", "fg": COLORS["cyan"], "border": "#03070C"},
        "hover": {"bg": "#102E40", "fg": "#FFFFFF", "border": COLORS["border"]},
        "active": {"bg": "#16465A", "fg": "#FFFFFF", "border": COLORS["cyan"]},
        "disabled": {"bg": "#03070C", "fg": COLORS["dim"], "border": "#03070C"},
    },
    "close": {
        "normal": {"bg": "#03070C", "fg": COLORS["cyan"], "border": "#03070C"},
        "hover": {"bg": COLORS["red"], "fg": "#FFFFFF", "border": COLORS["red"]},
        "active": {"bg": "#B82C46", "fg": "#FFFFFF", "border": COLORS["red"]},
        "disabled": {"bg": "#03070C", "fg": COLORS["dim"], "border": "#03070C"},
    },
}

ASSETS = {
    "logo": "assets/app/image/logo.png",
    "logo_text": "assets/app/image/logoWText.png",
    "dashboard": "assets/app/image/dashboard.png",
    "welcome": "assets/app/image/welcome.png",
    "icon.add": "assets/app/icons/add256.png",
    "icon.capture_target": "assets/app/icons/capture_target.png",
    "icon.view_eye": "assets/app/icons/view_eye.png",
    "icon.trash_junk": "assets/app/icons/trash_junk256.png",
    "icon.restore_settings": "assets/app/icons/restore_settings256.png",
}

DEFAULT_SETTINGS = {
    "ping": 100,
    "iguanadon": "GACHAIGUANADON",
    "bed_spawn": "GACHARENDER",
    "berry_station": "GACHABERRYSTATION",
    "berry_type": "mejoberry",
    "time_to_reberry": 30,
    "station_yaw": 0.0,
    "server_number": "0",
    "auto_start_program": False,
    "singleplayer": False,
    "external_berry": False,
    "iguanadon_seed_throw_amount": 18,
    "gacha_feed_delay": 6600,
    "allow_focus_ark_window": True,
    "focus_ark_window_interval": 5.0,
    "helper_inactive_opacity": 0.3,
    "launcher_width": 1200,
    "launcher_height": 800,
}

TEMPLATE_SETTING_KEYS = tuple(key for key in DEFAULT_SETTINGS if key != "station_yaw")
TEMPLATE_REFERENCE_DEFAULTS = {
    **{f"{key}_template": "" for key in TEMPLATE_SETTING_KEYS},
    "dedis_template": "",
    "gacha_template": "",
    "pego_template": "",
}

HIDDEN_SETTINGS = set()

SETTING_LABELS = {
    "ping": "Server ping",
    "server_number": "Server",
    "auto_start_program": "Auto start program",
    "singleplayer": "Singleplayer",
    "iguanadon": "Iguanadon",
    "bed_spawn": "Bed spawn",
    "berry_station": "Berry station",
    "berry_type": "Berry name",
    "time_to_reberry": "Reberry after",
    "station_yaw": "Station yaw",
    "external_berry": "Troughs away?",
    "iguanadon_seed_throw_amount": "Seed drop",
    "gacha_feed_delay": "Gacha feed delay",
    "helper_inactive_opacity": "Helper inactive opacity",
    "allow_focus_ark_window": "Allow Ark window focus",
    "focus_ark_window_interval": "Ark window focus interval",
    "launcher_width": "Launcher startup width",
    "launcher_height": "Launcher startup height",
    "check_on_every_dedi": "Check every N dedis",
}


def setting_label(key):
    return SETTING_LABELS.get(key, key.replace("_", " ").capitalize())


SETTING_TOOLTIPS = {
    "server_number": "Server number where you built Gacha Tower.",
    "singleplayer": "Is this running in Single player mode?",
    "bed_spawn": (
        "AKA Render station, where you will respawn, render, the center of your tower."
    ),
    "iguanadon_seed_throw_amount": (
        "Stack amount of seed that will be deleted after Iguanodon process. "
        "This helps make sure Gacha still have space to pickup SnowOwl pells. "
        "Suggest leaving it to 0 if your Iguanodon weight <= 1500."
    ),
    "berry_type": (
        "Mejoberry, Narco, etc, what will be searched before transfer to "
        "Iguanodon. This makes sure only berry will be consumed, no other else."
    ),
    "time_to_reberry": "How long should we refill berry from troughs to iguanodon? Put 0(second) to make it refill everytime",
    "external_berry": (
        "Check this if your berry station is far away from the Render station."
    ),
}


def setting_tooltip(key):
    return SETTING_TOOLTIPS.get(key, "")


SETTINGS_GROUPS = {
    "SERVER": [
        "server_number",
        "ping",
        "singleplayer",
    ],
    "STATIONS": [
        "bed_spawn",
        "station_yaw",
        "iguanadon",
        "iguanadon_seed_throw_amount",
        "berry_station",
        "berry_type",
        "time_to_reberry",
        "external_berry",
    ],
    "PEGO": [],
    "DEDI": [],
    "GACHA": [
        "gacha_feed_delay",
    ],
    "LAUNCHER": [
        "auto_start_program",
        "helper_inactive_opacity",
        "allow_focus_ark_window",
        "focus_ark_window_interval",
        "launcher_width",
        "launcher_height",
    ],
}

TEMPLATE_GROUP_SETTING_KEYS = {
    "SERVER": tuple(SETTINGS_GROUPS["SERVER"]),
    "STATIONS": tuple(
        key for key in SETTINGS_GROUPS["STATIONS"] if key != "station_yaw"
    ),
    "GACHA": tuple(SETTINGS_GROUPS["GACHA"]),
    "LAUNCHER": tuple(SETTINGS_GROUPS["LAUNCHER"]),
}

TEMPLATE_GROUP_REFERENCE_KEYS = {
    **{
        group: tuple(f"{key}_template" for key in keys)
        for group, keys in TEMPLATE_GROUP_SETTING_KEYS.items()
    },
    "DEDI": ("dedis_template",),
    "GACHA": ("gacha_feed_delay_template", "gacha_template"),
    "PEGO": ("pego_template",),
}
