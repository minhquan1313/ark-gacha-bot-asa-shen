import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from source.gacha_bot import server_transfer
from source.launcher.runner_overlay import TransferRunnerOverlay


class TransferProgressTests(unittest.TestCase):
    def test_title_refresh_preserves_tasks_and_waits_for_explicit_refresh(self):
        """Deposits change the set while title snapshots retain the loop count."""
        snapshots = []
        inventory = SimpleNamespace(g_last_check_can_transfer=True)
        dedis = {
            "resource": {"items": [{}]},
            "destination": {"teleport": "DEST", "items": [{}, {}, {}]},
        }
        with patch.multiple(
            server_transfer,
            list_of_full_dedi=set(),
            teleporter=Mock(),
            utils=Mock(),
            dedi=SimpleNamespace(open_deposit_all=Mock(return_value=True)),
            player_inventory=inventory,
        ):
            tracker = server_transfer.TransferTaskTracker(
                ["Deposit", "Next"], snapshots.append,
                destination_dedi_total=len(dedis["destination"]["items"]),
            )
            tracker.refresh_overlay_title(0, len(dedis["destination"]["items"]))
            tracker.start("Deposit")
            self.assertTrue(server_transfer.deposit_to_transfer_dedis(dedis))
            self.assertEqual(len(snapshots), 2)
            tracker.start("Next")
            self.assertEqual(snapshots[-1]["destination_dedi_count"], 0)
            tracker.refresh_overlay_title(len(server_transfer.list_of_full_dedi), 3)
            self.assertEqual([s["destination_dedi_count"] for s in snapshots], [0, 0, 0, 3])
            self.assertTrue(all(s["destination_dedi_total"] == 3 for s in snapshots))
            self.assertEqual(snapshots[-1]["running"], snapshots[-2]["running"])
            self.assertEqual(snapshots[-1]["active"], snapshots[-2]["active"])
            self.assertEqual(server_transfer.list_of_full_dedi, {0, 1, 2})
            # The final dedi is revisited by existing deposit logic; adding its
            # existing index must not increase the next loop's title count.
            server_transfer.deposit_to_transfer_dedis(dedis)
            self.assertEqual(len(snapshots), 4)
            tracker.refresh_overlay_title(len(server_transfer.list_of_full_dedi), 3)
            self.assertEqual(len(snapshots), 5)
            self.assertEqual(snapshots[-1]["destination_dedi_count"], 3)

    def test_overlay_title_loading_pause_resume_and_new_run(self):
        """The header and native title share progress across runner states."""
        app = QApplication.instance() or QApplication([])
        owner = SimpleNamespace(
            screen=lambda: None, runner_state="RUNNING",
            transfer_task_snapshot={"destination_dedi_count": 0, "destination_dedi_total": 5},
        )
        overlay = TransferRunnerOverlay(owner)
        try:
            self.assertEqual(overlay.windowTitle(), "TransGbot[0/5]")
            overlay.refresh_loading()
            self.assertEqual(overlay.header_title.text(), "TransGbot[0/5]")
            snapshot = {"destination_dedi_count": 2, "destination_dedi_total": 5,
                        "running": [], "active": [], "waiting": []}
            for state in ("RUNNING", "PAUSED", "RUNNING"):
                owner.runner_state = state
                overlay.refresh(snapshot)
                self.assertEqual(overlay.windowTitle(), "TransGbot[2/5]")
                self.assertEqual(overlay.header_title.text(), "TransGbot[2/5]")
            overlay.update_destination_progress(owner.transfer_task_snapshot)
            overlay.refresh_loading()
            app.processEvents()
            self.assertEqual(overlay.windowTitle(), "TransGbot[0/5]")
            self.assertEqual(overlay.header_title.text(), "TransGbot[0/5]")
        finally:
            overlay.close()


if __name__ == "__main__":
    unittest.main()
