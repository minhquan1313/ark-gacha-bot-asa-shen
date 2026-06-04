import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]


def load_render_module():
    settings = types.SimpleNamespace(lag_offset=1, station_yaw=-78.57)
    pyautogui = types.SimpleNamespace(keyDown=Mock(), keyUp=Mock())
    buffs = types.SimpleNamespace(
        check_buffs=Mock(return_value=types.SimpleNamespace(check_buffs=Mock(return_value=0)))
    )
    player_inventory = types.SimpleNamespace(implant_eat=Mock())
    player_state = types.SimpleNamespace(
        check_state=Mock(),
        human=types.SimpleNamespace(on_tp=False),
        reset_state=Mock(),
    )
    player = types.ModuleType("source.ASA.player")
    player.buffs = buffs
    player.player_inventory = player_inventory
    player.player_state = player_state
    stations = types.ModuleType("source.ASA.stations")
    stations.custom_stations = types.SimpleNamespace()
    structures = types.ModuleType("source.ASA.strucutres")
    structures.inventory = types.SimpleNamespace()
    structures.teleporter = types.SimpleNamespace(teleport_not_default=Mock())
    utility = types.ModuleType("source.utility")
    utility.local_player = types.SimpleNamespace(
        get_input_settings=Mock(side_effect=lambda value: value)
    )
    utility.screen = types.SimpleNamespace()
    utility.template = types.SimpleNamespace(
        check_template_no_bounds=Mock(),
        template_await_true=Mock(return_value=True),
    )
    utility.utils = types.SimpleNamespace(
        keymap_return=Mock(return_value=69),
        press_key=Mock(),
        set_yaw=Mock(),
        turn_down=Mock(),
        zero=Mock(),
    )
    utility.variables = types.SimpleNamespace(get_pixel_loc=Mock(return_value=0))
    utility.windows = types.SimpleNamespace(move_mouse=Mock())
    logs = types.ModuleType("source.logs.gachalogs")
    logs.logger = Mock()

    modules = {
        "pyautogui": pyautogui,
        "settings": settings,
        "source.gacha_bot.config": types.SimpleNamespace(render_attempts=3),
        "source.ASA.player": player,
        "source.ASA.stations": stations,
        "source.ASA.strucutres": structures,
        "source.logs.gachalogs": logs,
        "source.utility": utility,
    }
    spec = importlib.util.spec_from_file_location(
        "render_under_test", ROOT / "source" / "gacha_bot" / "render.py"
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    module.time.sleep = Mock()
    return module, settings, utility.utils


class RenderSettingsTests(unittest.TestCase):
    def test_leave_tekpod_uses_station_yaw_without_render_pushout(self):
        render, settings, utils = load_render_module()

        render.leave_tekpod()

        self.assertFalse(hasattr(settings, "render_pushout"))
        utils.set_yaw.assert_called_once_with(settings.station_yaw)
        self.assertFalse(hasattr(utils, "current_yaw"))


if __name__ == "__main__":
    unittest.main()
