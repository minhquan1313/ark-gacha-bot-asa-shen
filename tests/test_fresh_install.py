"""Missing configuration files must be created without relying on shipped user data."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from source.gacha_bot.craft_config import load_craft_config
from source.gacha_bot.deposit_config import load_deposit_config
from source.launcher.config import auto_feed_config
from source.launcher.config.station_config import load_gacha_collect_config, load_gacha_config, load_pego_config
from source.launcher.config.transfer_helper_config import (
    load_transfer_dedis,
    load_transfer_players,
    load_transfer_settings,
)
from source.launcher.utils.auto_join_server_store import load_auto_join_afk_join, load_auto_join_servers
from source.launcher.utils.settings_store import load_settings
from source.launcher.utils.vault_items_store import DEFAULT_VAULT_ITEMS, load_vault_items


ROOT = Path(__file__).resolve().parents[1]


class FreshInstallTests(unittest.TestCase):
    def run_isolated(self, script: str):
        """Execute imports in a fresh process with no user JSON or desktop activity."""
        with tempfile.TemporaryDirectory(prefix="gbot fresh install ") as directory:
            root = Path(directory)
            # Production logging directories are shipped independently of user JSON.
            (root / "source/logs").mkdir(parents=True)
            (root / "source/join_sim/source/logs").mkdir(parents=True)
            env = dict(os.environ, PYTHONPATH=str(ROOT), QT_QPA_PLATFORM="offscreen")
            result = subprocess.run([sys.executable, "-c", script], cwd=root, env=env,
                                    capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_settings_import_creates_defaults_and_preserves_saved_values(self):
        self.run_isolated('''
import importlib, json
from pathlib import Path
assert not Path('json_files').exists()
import settings
path = Path('json_files/settings.json')
data = json.loads(path.read_text())
assert settings.ping == data['ping'] == 100
assert data['auto_start_program'] is False
assert data['auto_keys']['enabled'] is False
data['ping'] = 321
path.write_text(json.dumps(data))
original = path.read_bytes()
importlib.reload(settings)
assert settings.ping == 321
assert path.read_bytes() == original
''')

    def test_console_import_creates_bounds_and_save_creates_parent(self):
        self.run_isolated('''
import importlib, json, sys, types
from pathlib import Path
sys.modules['source.utility.screen'] = types.ModuleType('source.utility.screen')
from source.utility import template
path = Path('json_files/console.json')
assert json.loads(path.read_text()) == [{'upper_bound': 145, 'lower_bound': 130}]
assert (template.lower_console_bound, template.upper_console_bound) == (130, 145)
template.set_bounds(110, 155)
original = path.read_bytes()
importlib.reload(template)
assert (template.lower_console_bound, template.upper_console_bound) == (110, 155)
assert path.read_bytes() == original
path.unlink()
path.parent.rmdir()
template.set_bounds(120, 150)
assert json.loads(path.read_text()) == [{'upper_bound': 150, 'lower_bound': 120}]
path.write_text('{broken')
assert template.get_file() == []
assert path.read_text() == '{broken'
''')

    def test_task_manager_creates_empty_station_files(self):
        self.run_isolated('''
import json, sys, types
from pathlib import Path
import source.gacha_bot
stations = types.ModuleType('source.gacha_bot.stations')
stations.BaseTask = object
sys.modules['source.gacha_bot.stations'] = stations
import task_manager
for name in ('gacha', 'gacha_collect', 'pego'):
    path = Path(f'json_files/{name}.json')
    assert task_manager.load_resolution_data(path) == []
    assert json.loads(path.read_text()) == []
    path.write_text('[{"teleporter":"CUSTOM"}]')
    original = path.read_bytes()
    assert task_manager.load_resolution_data(path) == [{'teleporter': 'CUSTOM'}]
    assert path.read_bytes() == original
''')

    def test_configuration_loaders_create_nested_files_only_when_missing(self):
        loaders = (
            ("settings", load_settings),
            ("gacha", load_gacha_config),
            ("gacha_collect", load_gacha_collect_config),
            ("pego", load_pego_config),
            ("craft", load_craft_config),
            ("deposit", load_deposit_config),
            ("transfer_settings", load_transfer_settings),
            ("transfer_dedis", load_transfer_dedis),
            ("transfer_players", load_transfer_players),
            ("auto_join", load_auto_join_servers),
            ("vault", lambda path: load_vault_items(path=path)),
        )
        with tempfile.TemporaryDirectory() as directory:
            for name, load in loaders:
                with self.subTest(config=name):
                    path = Path(directory) / name / "config.json"
                    value = load(path)
                    original = path.read_bytes()
                    self.assertEqual(load(path), value)
                    self.assertEqual(path.read_bytes(), original)
                    if name in ("gacha", "gacha_collect", "pego", "auto_join"):
                        self.assertEqual(value, [])
                    if name == "auto_join":
                        self.assertEqual(json.loads(original), {"last_join": [], "afk_join": False})
                        self.assertFalse(load_auto_join_afk_join(path))
                    if name == "vault":
                        self.assertEqual(value, sorted(DEFAULT_VAULT_ITEMS, key=str.lower))

    def test_auto_feed_creates_defaults_without_overwriting_malformed_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auto_feed/data.json"
            with patch.object(auto_feed_config, "AUTO_FEED_PATH", path):
                self.assertEqual(auto_feed_config.load_auto_feed(), auto_feed_config.DEFAULT_AUTO_FEED)
                self.assertEqual(json.loads(path.read_text()), auto_feed_config.DEFAULT_AUTO_FEED)
                path.write_text('{broken')
                auto_feed_config.load_auto_feed()
                self.assertEqual(path.read_text(), '{broken')

    def test_no_write_modes_do_not_create_files(self):
        with tempfile.TemporaryDirectory() as directory:
            for load in (load_gacha_config, load_gacha_collect_config, load_pego_config,
                         load_craft_config, load_deposit_config, load_transfer_settings,
                         load_transfer_dedis, load_transfer_players):
                with self.subTest(loader=load.__name__):
                    path = Path(directory) / load.__name__ / "config.json"
                    load(path, create_missing=False)
                    self.assertFalse(path.exists())

    def test_launcher_builds_all_pages_without_user_json(self):
        self.run_isolated('''
import sys, types
from pathlib import Path
from unittest.mock import patch
assert not Path('json_files').exists()
sys.modules['mss'] = types.ModuleType('mss')
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from source.launcher.gui import SettingsGUI
from source.launcher.components.gallery import CoverGallery
app = QApplication([])
errors, ready = [], []
with patch.object(SettingsGUI, '_start_background_services'), \\
     patch.object(SettingsGUI, '_register_start_stop_hotkey'), \\
     patch.object(SettingsGUI, '_register_auto_keys_stop_hotkey'), \\
     patch.object(SettingsGUI, 'load_previous_logs'), \\
     patch.object(CoverGallery, 'run_work'):
    window = SettingsGUI(deferred_startup=True)
    window.startup_failed.connect(lambda error: (errors.append(error), app.quit()))
    window.startup_ready.connect(lambda: (ready.append(True), app.quit()))
    QTimer.singleShot(15000, app.quit)
    app.exec()
    assert not errors, errors
    assert ready, 'Startup did not finish'
    assert window.pages, 'No launcher pages constructed'
    for group in ('SERVER', 'STATIONS', 'PEGO', 'GACHA', 'DEDI', 'CRAFT', 'LAUNCHER'):
        window._render_settings_group(group)
    assert window.pego_config == []
    window._shutdown_resources()
    window.close()
assert Path('json_files/settings.json').exists()
assert not Path('json_files/template_settings').exists()
assert not Path('json_files/ark_start_game_restore.json').exists()
''')


if __name__ == "__main__":
    unittest.main()
