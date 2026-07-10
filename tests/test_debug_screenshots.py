import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from source.utility import debug_screenshots


ROOT = Path(__file__).resolve().parents[1]


class FakeRequestQueue:
    def __init__(self):
        self.messages = []

    def put(self, message):
        self.messages.append(message)


class FakeProcess:
    def __init__(self, alive=True):
        self.alive = alive
        self.join_calls = []
        self.terminated = False

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        self.join_calls.append(timeout)

    def terminate(self):
        self.terminated = True
        self.alive = False


class DebugScreenshotHelperTests(unittest.TestCase):
    def tearDown(self):
        debug_screenshots._reset_for_tests()

    def test_disabled_capture_is_noop_and_does_not_start_worker(self):
        capture = debug_screenshots.capture_for("test")

        with patch.object(debug_screenshots, "_start_worker") as start_worker:
            capture("ignored")

        start_worker.assert_not_called()

    def test_disabled_capture_ignores_delay(self):
        capture = debug_screenshots.capture_for("test", delay=5)

        with patch.object(debug_screenshots, "_start_worker") as start_worker:
            with patch.object(debug_screenshots.time, "sleep") as sleep:
                capture("ignored")

        sleep.assert_not_called()
        start_worker.assert_not_called()

    def test_enabled_capture_starts_worker_lazily(self):
        request_queue = FakeRequestQueue()
        state = debug_screenshots._WorkerState(
            request_queue=request_queue,
            process=FakeProcess(),
        )
        with patch.object(
            debug_screenshots, "_start_worker", return_value=state
        ) as start_worker:
            capture = debug_screenshots.capture_for("test_category", active=True)
            start_worker.assert_not_called()

            capture("Test Label")

        start_worker.assert_called_once_with()
        self.assertEqual(request_queue.messages[0]["category"], "test_category")
        self.assertEqual(request_queue.messages[0]["label"], "Test Label")
        self.assertEqual(request_queue.messages[0]["delay"], 0.5)

    def test_enabled_capture_with_delay_queues_without_main_process_sleep(self):
        request_queue = FakeRequestQueue()
        state = debug_screenshots._WorkerState(
            request_queue=request_queue,
            process=FakeProcess(),
        )
        with patch.object(debug_screenshots.time, "sleep") as sleep:
            with patch.object(debug_screenshots, "_start_worker", return_value=state):
                capture = debug_screenshots.capture_for(
                    "test_category", active=True, delay=1.25
                )
                capture("Test Label")

        sleep.assert_not_called()
        self.assertEqual(request_queue.messages[0]["category"], "test_category")
        self.assertEqual(request_queue.messages[0]["label"], "Test Label")
        self.assertEqual(request_queue.messages[0]["delay"], 1.25)

    def test_negative_delay_behaves_as_zero(self):
        request_queue = FakeRequestQueue()
        state = debug_screenshots._WorkerState(
            request_queue=request_queue,
            process=FakeProcess(),
        )
        with patch.object(debug_screenshots, "_start_worker", return_value=state):
            capture = debug_screenshots.capture_for(
                "test_category", active=True, delay=-1
            )
            capture("Test Label")

        self.assertEqual(request_queue.messages[0]["delay"], 0.0)

    def test_worker_captures_only_after_due_time(self):
        pending = [(12.0, 0, "test_category", "Test Label")]
        capturer = Mock()

        with patch.object(debug_screenshots.time, "monotonic", return_value=11.0):
            result = debug_screenshots._capture_due_requests(
                pending, capturer, "root", "run"
            )

        self.assertIs(result, capturer)
        capturer.capture.assert_not_called()
        self.assertEqual(pending, [(12.0, 0, "test_category", "Test Label")])

        with patch.object(debug_screenshots.time, "monotonic", return_value=12.0):
            result = debug_screenshots._capture_due_requests(
                pending, capturer, "root", "run"
            )

        self.assertIs(result, capturer)
        capturer.capture.assert_called_once_with("test_category", "Test Label")
        self.assertEqual(pending, [])

    def test_next_queue_timeout_uses_next_due_capture(self):
        pending = [(12.0, 0, "test_category", "Test Label")]

        with patch.object(debug_screenshots.time, "monotonic", return_value=11.75):
            self.assertEqual(debug_screenshots._next_queue_timeout(pending), 0.25)

    def test_stop_terminates_stuck_worker(self):
        request_queue = FakeRequestQueue()
        process = FakeProcess(alive=True)
        debug_screenshots._state = debug_screenshots._WorkerState(
            request_queue=request_queue,
            process=process,
        )

        debug_screenshots.stop_debug_screenshot_worker()

        self.assertEqual(request_queue.messages, [None])
        self.assertTrue(process.terminated)

    def test_cleanup_disabled_leaves_debug_screenshots_untouched(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            old_file = root / "old.png"
            old_file.write_text("old", encoding="utf-8")

            with patch.object(debug_screenshots, "DEBUG_SCREENSHOT_ROOT", root):
                with patch.object(debug_screenshots, "IS_CLEANUP_ONSTART", False):
                    debug_screenshots.cleanup_debug_screenshots_on_program_start()

            self.assertTrue(old_file.exists())

    def test_cleanup_enabled_deletes_children_but_keeps_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            old_folder = root / "old_run"
            old_folder.mkdir()
            (old_folder / "old.png").write_text("old", encoding="utf-8")
            old_file = root / "loose.png"
            old_file.write_text("old", encoding="utf-8")

            with patch.object(debug_screenshots, "DEBUG_SCREENSHOT_ROOT", root):
                with patch.object(debug_screenshots, "IS_CLEANUP_ONSTART", True):
                    debug_screenshots.cleanup_debug_screenshots_on_program_start()

            self.assertTrue(root.exists())
            self.assertFalse(old_folder.exists())
            self.assertFalse(old_file.exists())

    def test_cleanup_runs_only_once_until_reset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            with patch.object(debug_screenshots, "DEBUG_SCREENSHOT_ROOT", root):
                with patch.object(debug_screenshots, "IS_CLEANUP_ONSTART", True):
                    debug_screenshots.cleanup_debug_screenshots_on_program_start()
                    later_file = root / "later.png"
                    later_file.write_text("later", encoding="utf-8")
                    debug_screenshots.cleanup_debug_screenshots_on_program_start()

            self.assertTrue(later_file.exists())

    def test_reset_for_tests_resets_cleanup_guard(self):
        debug_screenshots._cleanup_done = True

        debug_screenshots._reset_for_tests()

        self.assertFalse(debug_screenshots._cleanup_done)


def _debug_capture_module():
    captures = {}
    debug = types.ModuleType("source.utility.debug_screenshots")
    debug.CAPTURE_DEDI_DEPOSIT_CRYSTAL = False
    debug.CAPTURE_DEDI_DEPOSIT_GRIND = False
    debug.CAPTURE_IGUANADON_SEED = False
    debug.CAPTURE_GACHA_SEED = False
    debug.CAPTURE_GACHA_OVERCAP = False
    debug.CAPTURE_PEGO_CRYSTAL = False
    debug.CAPTURE_ROUTE_READY = False
    debug.CAPTURE_GRINDER_WITHDRAW = False
    debug.CAPTURE_VAULT_TRANSFER = False

    def capture_for(category, active=False, delay=0.0):
        captures[category] = Mock()
        return captures[category]

    debug.capture_for = capture_for
    return debug, captures


def load_gacha_module():
    debug, captures = _debug_capture_module()
    inventory = types.SimpleNamespace(
        close=Mock(),
        drop_all_obj=Mock(),
        is_open=Mock(return_value=True),
        open=Mock(),
        search_in_object=Mock(),
        transfer_all_from=Mock(),
        wait_clear_search=Mock(),
        was_server_lag_last_open=False,
    )
    player_inventory = types.SimpleNamespace(
        close=Mock(),
        open=Mock(),
        search_in_inventory=Mock(),
        transfer_all_inventory=Mock(),
    )
    template = types.SimpleNamespace(
        check_template=Mock(return_value=False),
        check_template_no_bounds=Mock(),
        template_await_true=Mock(),
    )
    utility = types.ModuleType("source.utility")
    utility.debug_screenshots = debug
    utility.local_player = types.SimpleNamespace()
    utility.screen = types.SimpleNamespace()
    utility.template = template
    utility.utils_simple = types.SimpleNamespace(
        get_default_clock=Mock(return_value=Mock(return_value=False))
    )
    utility.utils = types.SimpleNamespace(
        get_default_clock=Mock(return_value=Mock(return_value=False)),
        move_mouse=Mock(),
        press_key=Mock(),
        set_yaw=Mock(),
        turn_left=Mock(),
        turn_right=Mock(),
        zero_center=Mock(),
        zero=Mock(),
    )
    utility.variables = types.SimpleNamespace(get_pixel_loc=Mock(return_value=0))
    utility.windows = types.SimpleNamespace(click=Mock(), move_mouse=Mock())

    structures = types.ModuleType("source.ASA.strucutres")
    structures.inventory = inventory
    structures.teleporter = types.SimpleNamespace()
    player = types.ModuleType("source.ASA.player")
    player.console = types.SimpleNamespace()
    player.player_inventory = player_inventory
    player.player_state = types.SimpleNamespace()
    gacha_structures = types.ModuleType("source.gacha_bot.structures")
    crop_plots = types.ModuleType("source.gacha_bot.structures.crop_plots")

    modules = {
        "settings": types.SimpleNamespace(
            berry_type="mejoberry", ping=1
        ),
        "source.logs.gachalogs": types.SimpleNamespace(logger=Mock()),
        "source.utility": utility,
        "source.utility.debug_screenshots": debug,
        "source.ASA.strucutres": structures,
        "source.ASA.player": player,
        "source.gacha_bot.config": types.SimpleNamespace(gacha_attempts=3),
        "source.gacha_bot.structures": gacha_structures,
        "source.gacha_bot.structures.crop_plots": crop_plots,
    }
    spec = importlib.util.spec_from_file_location(
        "gacha_under_test", ROOT / "source" / "gacha_bot" / "gacha.py"
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    module.time.sleep = Mock()
    return module, captures, template, inventory


def load_pego_module():
    debug, captures = _debug_capture_module()
    inventory = types.SimpleNamespace(
        close=Mock(),
        is_open=Mock(return_value=True),
        open=Mock(),
        search_in_object=Mock(),
        transfer_all_from=Mock(),
    )
    player_inventory = types.SimpleNamespace(
        drop_all_inv=Mock(), is_can_drop=Mock(return_value=False)
    )
    utility = types.ModuleType("source.utility")
    utility.debug_screenshots = debug
    utility.local_player = types.SimpleNamespace()
    utility.screen = types.SimpleNamespace()
    utility.template = types.SimpleNamespace(
        check_template=Mock(return_value=True),
        template_await_true=Mock(return_value=True),
    )
    utility.utils_simple = types.SimpleNamespace(
        get_default_clock=Mock(return_value=Mock(return_value=False))
    )
    utility.utils = types.SimpleNamespace(
        current_pitch=15,
        set_yaw=Mock(),
        turn_down=Mock(),
        turn_up=Mock(),
        zero_center=Mock(),
        zero=Mock(),
    )
    utility.variables = types.SimpleNamespace()
    utility.windows = types.SimpleNamespace()

    structures = types.ModuleType("source.ASA.strucutres")
    structures.inventory = inventory
    structures.teleporter = types.SimpleNamespace()
    player = types.ModuleType("source.ASA.player")
    player.player_inventory = player_inventory
    player.player_state = types.SimpleNamespace()

    modules = {
        "settings": types.SimpleNamespace(ping=1),
        "source.logs.gachalogs": types.SimpleNamespace(logger=Mock()),
        "source.utility": utility,
        "source.utility.debug_screenshots": debug,
        "source.ASA.strucutres": structures,
        "source.ASA.player": player,
        "source.gacha_bot.config": types.SimpleNamespace(pego_attempts=3),
    }
    spec = importlib.util.spec_from_file_location(
        "pego_under_test", ROOT / "source" / "gacha_bot" / "pego.py"
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    module.time.sleep = Mock()
    return module, captures, inventory


class DebugCapturePointTests(unittest.TestCase):
    def test_gacha_nocrop_captures_seed_deposit(self):
        gacha, captures, template, _inventory = load_gacha_module()
        template.template_await_true.side_effect = [False, True]

        gacha.drop_off_nocrop("gacha1", "left")

        captures["gacha_seed_deposit"].assert_called_once_with("gacha1_left")

    def test_gacha_nocrop_captures_overcap_before_drop(self):
        gacha, captures, template, _inventory = load_gacha_module()
        template.template_await_true.side_effect = [True, True, True]

        gacha.drop_off_nocrop("gacha1", "right")

        captures["gacha_overcap_before_drop"].assert_called_once_with("gacha1_right")

    def test_gacha_drop_off_nocrop_captures_seed_deposit(self):
        gacha, captures, _template, _inventory = load_gacha_module()

        gacha.drop_off_nocrop("gacha2", "right")

        captures["gacha_seed_deposit"].assert_called_once_with("gacha2_right")

    def test_pego_pickup_captures_crystal_withdraw(self):
        pego, captures, inventory = load_pego_module()

        pego.pego_pickup("pego1")

        captures["pego_crystal_withdraw"].assert_called_once_with("pego1")
        inventory.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
