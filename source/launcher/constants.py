SETTINGS_FILE = "json_files/settings.json"
GACHA_LOG_FILE = "source/logs/logs.txt"
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
}

DEFAULT_SETTINGS = {
    "screen_resolution": "VALUE DOES NOT MATTER",
    "base_path": "VALUE DOES NOT MATTER",
    "lag_offset": 1.0,
    "iguanadon": "GACHAIGUANADON",
    "drop_off": "GACHADEDI",
    "bed_spawn": "GACHARENDER",
    "berry_station": "GACHABERRYSTATION",
    "grindables": "GACHAGRINDABLES",
    "berry_type": "mejoberry",
    "station_yaw": 0.0,
    "render_pushout": 0.0,
    "height_ele": 3,
    "height_grind": 3,
    "server_number": "0",
    "auto_start_program": False,
    "singleplayer": False,
    "external_berry": False,
    "crafting": False,
    "seeds_230": False,
    "side_crop_plot": False,
    "y_trap_bot": False,
    "allow_focus_ark_window": True,
    "focus_ark_window_interval": 5.0,
    "helper_inactive_opacity": 0.3,
    "dedi_handshake_timeout": 180,
}

HIDDEN_SETTINGS = {
    "drop_off",
    "grindables",
    "height_ele",
    "height_grind",
}

SETTINGS_GROUPS = {
    "GENERAL": [
        "screen_resolution",
        "base_path",
        "lag_offset",
        "server_number",
        "auto_start_program",
    ],
    "DINO / STATION NAMES": [
        "iguanadon",
        "bed_spawn",
        "berry_station",
        "berry_type",
    ],
    "UI": [
        "helper_inactive_opacity",
    ],
    "POSITION / RENDER": [
        "station_yaw",
        "render_pushout",
    ],
    "STORAGE": [],
    "FEATURES": [
        "singleplayer",
        "external_berry",
        "crafting",
        "seeds_230",
        "side_crop_plot",
        "y_trap_bot",
        "allow_focus_ark_window",
        "focus_ark_window_interval",
    ],
}
