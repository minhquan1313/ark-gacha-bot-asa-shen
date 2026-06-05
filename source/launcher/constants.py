SETTINGS_FILE = "json_files/settings.json"
GACHA_LOG_FILE = "source/logs/logs.txt"
MAX_LAUNCHER_LOG_LINES = 2000
APP_NAME = "Shen GBot"
APP_TITLE = APP_NAME.upper()
APP_VERSION = "v1.0.0"
SUPPORTED_GAME_RESOLUTIONS = {(1920, 1080)}
GAME_WINDOW_TITLE = "ArkAscended"
BUTTON_TRANSITION_MS = 200
BREAKPOINT_NARROW_WIDTH = 720
PC_MINIMUM_SIZE = (1180, 680)
PHONE_MINIMUM_SIZE = (420, 640)
TITLE_BAR_HEIGHT = 42
WINDOW_RESIZE_BORDER_PX = 8
ENABLE_NATIVE_CUSTOM_CHROME = True

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
    "icon.trash_junk": "assets/app/icons/trash_junk.png",
    "icon.restore_settings": "assets/app/icons/restore_settings.png",
}

DEFAULT_SETTINGS = {
    "lag_offset": 1.0,
    "iguanadon": "GACHAIGUANADON",
    "bed_spawn": "GACHARENDER",
    "berry_station": "GACHABERRYSTATION",
    "berry_type": "mejoberry",
    "station_yaw": 0.0,
    "server_number": "0",
    "auto_start_program": False,
    "singleplayer": False,
    "external_berry": False,
    "seeds_230": False,
    "gacha_feed_delay": 6600,
    "gacha_230_feed_delay": 10700,
    "side_crop_plot": False,
    "allow_focus_ark_window": True,
    "focus_ark_window_interval": 5.0,
    "helper_inactive_opacity": 0.3,
    "launcher_width": 1200,
    "launcher_height": 800,
    "dedi_handshake_timeout": 30,
}

HIDDEN_SETTINGS = {
    "seeds_230",
    "gacha_230_feed_delay",
}

SETTING_LABELS = {
    "lag_offset": "Lag offset",
    "server_number": "Server number",
    "auto_start_program": "Auto start program",
    "singleplayer": "Singleplayer",
    "iguanadon": "Iguanadon",
    "bed_spawn": "Bed & teleport",
    "berry_station": "Berry station",
    "berry_type": "Berry type",
    "station_yaw": "Station yaw",
    "external_berry": "Troughs far away",
    "seeds_230": "Seeds 230",
    "gacha_feed_delay": "Gacha feed delay",
    "gacha_230_feed_delay": "Gacha 230 feed delay",
    "side_crop_plot": "Side crops plot",
    "helper_inactive_opacity": "Helper inactive opacity",
    "allow_focus_ark_window": "Allow Ark window focus",
    "focus_ark_window_interval": "Ark window focus interval",
    "dedi_handshake_timeout": "Dedi handshake timeout",
    "launcher_width": "Launcher startup width",
    "launcher_height": "Launcher startup height",
}


def setting_label(key):
    return SETTING_LABELS.get(key, key.replace("_", " ").capitalize())


SETTINGS_GROUPS = {
    "GENERAL": [
        "lag_offset",
        "server_number",
        "auto_start_program",
        "singleplayer",
    ],
    "STATIONS": [
        "iguanadon",
        "bed_spawn",
        "berry_station",
        "berry_type",
    ],
    "POSITION / RENDER": [
        "station_yaw",
    ],
    "PEGO": [],
    "STORAGE": [],
    "GACHA": [],
    "FEATURES": [
        "external_berry",
        "side_crop_plot",
        "gacha_feed_delay",
    ],
    "WINDOW / HELPERS": [
        "helper_inactive_opacity",
        "allow_focus_ark_window",
        "focus_ark_window_interval",
        "launcher_width",
        "launcher_height",
    ],
}
