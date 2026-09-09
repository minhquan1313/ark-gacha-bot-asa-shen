import subprocess
import sys
import unittest
from unittest.mock import patch

from source.launcher import ark_game_setup
from source.launcher.utils import steam_accounts, update_service
from source.utility import utils_simple


@unittest.skipUnless(sys.platform == "win32", "Windows console flags")
class BackgroundProcessVisibilityTests(unittest.TestCase):
    def test_worker_retains_existing_flags_pipes_and_app_identifier(self):
        with patch.object(utils_simple.subprocess, "Popen") as popen:
            utils_simple.start_subprocess(
                [sys.executable, "-m", "example"], stdout=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        self.assertEqual(popen.call_args.args[0][-2:], ["--app-id", utils_simple.APP_ID])
        self.assertEqual(popen.call_args.kwargs["stdout"], subprocess.PIPE)
        self.assertEqual(
            popen.call_args.kwargs["creationflags"],
            subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
        )

    def test_updater_and_background_commands_suppress_console_windows(self):
        for module, function, arguments in (
            (update_service, update_service._run_updater, ("/check",)),
            (ark_game_setup, ark_game_setup.kill_running_ark, ()),
            (steam_accounts, steam_accounts.close_steam, ()),
        ):
            with self.subTest(function=function.__name__), patch.object(module.subprocess, "run") as run:
                function(*arguments)
                self.assertEqual(run.call_args.kwargs["creationflags"], subprocess.CREATE_NO_WINDOW)
        for module, function in (
            (ark_game_setup, ark_game_setup.launch_ark_through_steam),
            (steam_accounts, steam_accounts.launch_steam),
        ):
            with self.subTest(function=function.__name__), patch.object(module.subprocess, "Popen") as popen:
                function()
                self.assertEqual(popen.call_args.kwargs["creationflags"], subprocess.CREATE_NO_WINDOW)
