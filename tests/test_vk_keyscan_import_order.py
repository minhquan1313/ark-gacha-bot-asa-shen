import importlib
import sys
import types
import unittest
from unittest.mock import patch


def remove_module(module_name):
    sys.modules.pop(module_name, None)
    parent_name, _, child_name = module_name.rpartition(".")
    parent = sys.modules.get(parent_name)
    if parent is not None and hasattr(parent, child_name):
        delattr(parent, child_name)


class VkKeyScanImportOrderTests(unittest.TestCase):
    def tearDown(self):
        remove_module("source.join_sim.source.utility.utils")
        remove_module("source.utility.utils")

    def test_join_sim_utils_does_not_mutate_global_vk_key_scan_a_signature(self):
        marker = [object()]
        fake_user32 = types.SimpleNamespace(
            VkKeyScanA=types.SimpleNamespace(argtypes=marker),
            VkKeyScanW=lambda _char: ord("a"),
        )
        fake_ctypes = types.SimpleNamespace(
            c_short=object(),
            c_wchar=object(),
            windll=types.SimpleNamespace(user32=fake_user32),
            WINFUNCTYPE=lambda *_types: lambda _spec: fake_user32.VkKeyScanW,
        )
        fake_windows = types.SimpleNamespace(hwnd=123)
        fake_local_player = types.SimpleNamespace(
            get_input_settings=lambda _action: "l"
        )

        with patch.dict(
            sys.modules,
            {
                "ctypes": fake_ctypes,
                "source.join_sim.source.utility.windows": fake_windows,
                "source.join_sim.source.utility.local_player": fake_local_player,
            },
        ):
            module = importlib.import_module("source.join_sim.source.utility.utils")

        self.assertIs(fake_user32.VkKeyScanA.argtypes, marker)
        self.assertEqual(module.keymap_return("a"), ord("a"))

    def test_main_utils_does_not_mutate_global_vk_key_scan_a_signature(self):
        marker = [object()]
        fake_user32 = types.SimpleNamespace(
            VkKeyScanA=types.SimpleNamespace(argtypes=marker),
            VkKeyScanW=lambda _char: ord("a"),
        )
        fake_ctypes = types.SimpleNamespace(
            c_short=object(),
            c_wchar=object(),
            windll=types.SimpleNamespace(user32=fake_user32),
            WINFUNCTYPE=lambda *_types: lambda _spec: fake_user32.VkKeyScanW,
        )
        fake_windows = types.SimpleNamespace(hwnd=123)
        fake_local_player = types.SimpleNamespace(
            get_input_settings=lambda _action: "l"
        )
        fake_console = types.SimpleNamespace()
        fake_player_state = types.SimpleNamespace()
        fake_logs = types.SimpleNamespace(
            logger=types.SimpleNamespace(
                warning=lambda *_args, **_kwargs: None,
                debug=lambda *_args, **_kwargs: None,
                error=lambda *_args, **_kwargs: None,
            )
        )

        with patch.dict(
            sys.modules,
            {
                "ctypes": fake_ctypes,
                "source.utility.windows": fake_windows,
                "source.utility.local_player": fake_local_player,
                "source.ASA.player.console": fake_console,
                "source.ASA.player.player_state": fake_player_state,
                "source.logs.gachalogs": fake_logs,
            },
        ):
            module = importlib.import_module("source.utility.utils")

        self.assertIs(fake_user32.VkKeyScanA.argtypes, marker)
        self.assertEqual(module.keymap_return("a"), ord("a"))


if __name__ == "__main__":
    unittest.main()
