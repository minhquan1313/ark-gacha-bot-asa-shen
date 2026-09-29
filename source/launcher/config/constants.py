import json
import re
from pathlib import Path

SETTINGS_FILE = "json_files/settings.json"
GACHA_LOG_FILE = "source/logs/logs.txt"
JOIN_LOG_FILE = "source/join_sim/source/logs/logs.txt"
MAX_LAUNCHER_LOG_LINES = 2000
APP_NAME = "Shen GBot"
APP_TITLE = APP_NAME.upper()
_MANIFEST_PATH = Path(__file__).resolve().parents[3] / "manifest.json"


def installed_version(path: Path = _MANIFEST_PATH):
    """Read the installed release label without inventing a fallback version."""
    try:
        version = json.loads(path.read_text(encoding="utf-8"))["version"]
        if not isinstance(version, str) or not re.fullmatch(r"[vV]?\d+\.\d+\.\d+", version.strip()):
            return "Unknown"
        return f"v{version.strip().lstrip('vV')}"
    except (OSError, KeyError, TypeError, ValueError):
        return "Unknown"


APP_VERSION = installed_version()
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

# Horizontal positions and dark-overlay opacities, both from 0.0 to 1.0.
# Edit these values to tune all cover/header images together.
COVER_OVERLAY_STOPS = ((0.0, 0.70), (0.5, 0.50), (1.0, 0.05))
# COVER_OVERLAY_STOPS = ((0.0, 0.50), (0.5, 0.20), (1.0, 0.05))
COVER_OVERLAY_COLOR = "#03121E"

TOGGLE_TRANSITION_MS = 220

ASSETS = {
    "about.hero": "assets/app/image/about/hero.png",
    "about.update": "assets/app/image/about/update.png",
    "about.illustration": "assets/app/image/about/illustration.png",
    "about.quote": "assets/app/image/about/quote.png",
    #
    "tools.cover": "assets/app/image/tools.png",
    #
    "btemplates.cover": "assets/app/image/build_templates.png",
    "btemplates.blueprint": "assets/app/image/build_templates_blueprint.svg",
    #
    "logo": "assets/app/image/logo.png",
    "logo_text": "assets/app/image/logoWText.png",
    "dashboard": "assets/app/image/dashboard.png",
    "welcome": "assets/app/image/welcome.png",
    #
    "settings.breadcrumb": "assets/app/image/settings/breadcrumb.png",
    "settings.breadcrumb.server": "assets/app/image/settings/breadcrumb_server.png",
    "settings.breadcrumb.stations": "assets/app/image/settings/breadcrumb_stations.png",
    "settings.breadcrumb.pego": "assets/app/image/settings/breadcrumb_pego.png",
    "settings.breadcrumb.dedi": "assets/app/image/settings/breadcrumb_dedi.png",
    "settings.breadcrumb.gacha": "assets/app/image/settings/breadcrumb_gacha.png",
    "settings.breadcrumb.craft": "assets/app/image/settings/breadcrumb_craft.png",
    "settings.breadcrumb.launcher": "assets/app/image/settings/breadcrumb_launcher.png",
    #
    "settings.pego_delays": "assets/app/image/settings/pego_delays.png",
    "settings.pego_list": "assets/app/image/settings/pego_list.png",
    #
    "settings.dedi_crystal": "assets/app/image/settings/dedi_crystal.png",
    "settings.dedi_grindable": "assets/app/image/settings/dedi_grindable.png",
    "settings.dedi_general": "assets/app/image/settings/dedi_general.png",
    #
    "settings.gacha": "assets/app/image/settings/gacha.png",
    "settings.gacha_collect": "assets/app/image/settings/gacha_collect.png",
    "settings.gacha_left": "assets/app/image/settings/gacha_left.png",
    "settings.gacha_right": "assets/app/image/settings/gacha_right.png",
    "settings.gacha_center": "assets/app/image/settings/gacha_center.png",
    #
    "settings.craft": "assets/app/image/settings/craft.png",
    #
    "settings.server": "assets/app/image/settings/server.png",
    #
    "settings.render": "assets/app/image/settings/render.png",
    "settings.iguanodon": "assets/app/image/settings/iguanodon.png",
    "settings.berry": "assets/app/image/settings/berry.png",
    #
    "settings.launcher": "assets/app/image/settings/launcher.png",
    "settings.auto_keys": "assets/app/image/settings/auto_keys.png",
    #
    "icon.craft": "assets/app/icons/craft.svg",
    "icon.pitch": "assets/app/icons/pitch.svg",
    "icon.sliders": "assets/app/icons/sliders.svg",
    "icon.crystal": "assets/app/icons/crystal_routes.svg",
    "icon.grindable": "assets/app/icons/grindable_routes.svg",
    "icon.locator": "assets/app/icons/locator.svg",
    "icon.plus": "assets/app/icons/plus.svg",
    "icon.pego": "assets/app/icons/pego.svg",
    "icon.more_vertical": "assets/app/icons/more_vertical.svg",
    "icon.copy": "assets/app/icons/copy.svg",
    "icon.calculator": "assets/app/icons/calculator.svg",
    "icon.launcher_settings": "assets/app/icons/launcher_settings.svg",
    "icon.auto_keys": "assets/app/icons/auto_keys.svg",
    "icon.iguanodon": "assets/app/icons/iguanodon.svg",
    "icon.add": "assets/app/icons/add256.png",
    "icon.capture_target": "assets/app/icons/capture_target.png",
    "icon.view_eye": "assets/app/icons/view_eye.png",
    "icon.trash_junk": "assets/app/icons/trash.svg",
    "icon.restore_settings": "assets/app/icons/restore_settings256.png",
    "icon.dashboard": "assets/app/icons/dashboard.svg",
    "icon.settings": "assets/app/icons/settings.svg",
    "icon.btemplates": "assets/app/icons/btemplates.svg",
    "icon.tools": "assets/app/icons/tools.svg",
    "icon.logs": "assets/app/icons/logs.svg",
    "icon.update": "assets/app/icons/update.svg",
    "icon.warning": "assets/app/icons/warning.svg",
    "icon.error": "assets/app/icons/error.svg",
    "icon.about": "assets/app/icons/about.svg",
    "icon.server": "assets/app/icons/server.svg",
    "icon.queue": "assets/app/icons/queue.svg",
    "icon.globe": "assets/app/icons/globe.svg",
    "icon.clock": "assets/app/icons/clock.svg",
    "icon.bolt": "assets/app/icons/bolt.svg",
    "icon.terminal": "assets/app/icons/terminal.svg",
    "icon.play": "assets/app/icons/play.svg",
    "icon.stop": "assets/app/icons/stop.svg",
    "icon.chip": "assets/app/icons/chip.svg",
    "icon.activity": "assets/app/icons/activity.svg",
    "icon.trash": "assets/app/icons/trash.svg",
    "icon.target": "assets/app/icons/target.svg",
    "icon.antenna": "assets/app/icons/antenna.svg",
    "icon.paw": "assets/app/icons/paw.svg",
    "icon.search": "assets/app/icons/search.svg",
    "icon.sort": "assets/app/icons/sort.svg",
    "icon.grid": "assets/app/icons/grid.svg",
    "icon.list": "assets/app/icons/list.svg",
    "icon.cube": "assets/app/icons/cube.svg",
    "icon.diamond": "assets/app/icons/diamond.svg",
    "icon.rocket": "assets/app/icons/rocket.svg",
    "icon.bed": "assets/app/icons/bed.svg",
    "icon.berry": "assets/app/icons/berry.svg",
    "icon.save": "assets/app/icons/save.svg",
    "icon.double_chevron": "assets/app/icons/double_chevron.svg",
    "icon.chevron_down": "assets/app/icons/chevron_down.svg",
    #
    "tool.auto_feed": "assets/app/image/auto_feed.png",
    "tool.auto_fertilizer": "assets/app/image/auto_fertilizer.png",
    "tool.auto_fishing": "assets/app/image/auto_fishing.png",
    "tool.auto_join": "assets/app/image/auto_join.png",
    "tool.switch_steam": "assets/app/image/switch_steam.png",
    "tool.transfer_server": "assets/app/image/transfer_server.png",
}

AUTO_KEYS_REPEAT_ACTIONS = ("Fire", "Use", "DropItem", "Crouch", "Jump")
KEY_HOLD_ACTIONS = ("MoveForward",)
AUTO_KEYS_ACTIONS = AUTO_KEYS_REPEAT_ACTIONS + KEY_HOLD_ACTIONS


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
    "gacha_collect_feed_delay": 6600,
    "allow_focus_ark_window": True,
    "focus_ark_window_interval": 5.0,
    "helper_inactive_opacity": 0.3,
    "launcher_width": 1200,
    "launcher_height": 800,
    "auto_keys": {
        "enabled": False,
        "activation_key": "F1",
        "interval": 0.25,
        "hold_duration": 1.0,
        "actions": {action: True for action in AUTO_KEYS_ACTIONS},
    },
}

TEMPLATE_SETTING_KEYS = tuple(key for key in DEFAULT_SETTINGS if key not in {"station_yaw", "auto_keys"})
TEMPLATE_REFERENCE_DEFAULTS = {
    **{f"{key}_template": "" for key in TEMPLATE_SETTING_KEYS},
    "dedis_template": "",
    "gacha_template": "",
    "gacha_collect_template": "",
    "craft_template": "",
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
    "gacha_collect_feed_delay": "Feed delay (s)",
    "helper_inactive_opacity": "Helper inactive opacity",
    "allow_focus_ark_window": "Allow Ark window focus",
    "focus_ark_window_interval": "Ark window focus interval",
    "launcher_width": "Launcher startup width",
    "launcher_height": "Launcher startup height",
    "check_on_every_dedi": "Check dedi",
}


def setting_label(key):
    return SETTING_LABELS.get(key, key.replace("_", " ").capitalize())


SETTING_TOOLTIPS = {
    "server_number": "Server number where you built Gacha Tower.",
    "singleplayer": "Is this running in Single player mode?",
    "bed_spawn": ("AKA Render station, where you will respawn, render, the center of your tower."),
    "iguanadon_seed_throw_amount": (
        "Stack amount of seed that will be deleted after Iguanodon process. "
        "This helps make sure Gacha still have space to pickup SnowOwl pells. "
        "Suggest leaving it to 0 if your Iguanodon weight <= 1500."
    ),
    "berry_type": ("Mejoberry, Narco, etc, what will be searched before transfer to Iguanodon. This makes sure only berry will be consumed, no other else."),
    "time_to_reberry": "How long should we refill berry from troughs to iguanodon? Put 0(second) to make it refill everytime",
    "external_berry": ("Check this if your berry station is far away from the Render station."),
}


def setting_tooltip(key):
    return SETTING_TOOLTIPS.get(key, "")


# Display names only; keep the group keys stable for settings and templates.
SETTINGS_GROUP_LABELS = {
    "SERVER": "Server",
    "STATIONS": "Stations",
    "PEGO": "Pego",
    "DEDI": "Dedi",
    "GACHA": "Gacha",
    "CRAFT": "Craft",
    "LAUNCHER": "Launcher",
}

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
    "GACHA": [
        "gacha_feed_delay",
        "gacha_collect_feed_delay",
    ],
    "DEDI": [],
    "CRAFT": [],
    "LAUNCHER": [
        "auto_start_program",
        "helper_inactive_opacity",
        "allow_focus_ark_window",
        "focus_ark_window_interval",
        "launcher_width",
        "launcher_height",
        "auto_keys",
    ],
}

TEMPLATE_GROUP_SETTING_KEYS = {
    "SERVER": tuple(SETTINGS_GROUPS["SERVER"]),
    "STATIONS": tuple(key for key in SETTINGS_GROUPS["STATIONS"] if key != "station_yaw"),
    "GACHA": tuple(SETTINGS_GROUPS["GACHA"]),
    "CRAFT": tuple(SETTINGS_GROUPS["CRAFT"]),
    "LAUNCHER": tuple(key for key in SETTINGS_GROUPS["LAUNCHER"] if key != "auto_keys"),
}

TEMPLATE_GROUP_REFERENCE_KEYS = {
    **{group: tuple(f"{key}_template" for key in keys) for group, keys in TEMPLATE_GROUP_SETTING_KEYS.items()},
    "DEDI": ("dedis_template",),
    "GACHA": (
        "gacha_feed_delay_template",
        "gacha_collect_feed_delay_template",
        "gacha_template",
        "gacha_collect_template",
    ),
    "CRAFT": ("craft_template",),
    "PEGO": ("pego_template",),
}

# Leave empty until the official site is available.
OFFICIAL_WEBSITE_URL = ""
