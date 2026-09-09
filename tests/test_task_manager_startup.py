import unittest
import sys
from types import ModuleType
from unittest.mock import Mock, patch

stations_stub = ModuleType("source.gacha_bot.stations")
stations_stub.base_task = object
sys.modules["source.gacha_bot.stations"] = stations_stub

import task_manager


class TaskManagerStartupTests(unittest.TestCase):
    def setUp(self) -> None:
        """Reset the scheduler singleton so preparation is isolated per test."""
        task_manager.SingletonMeta._instances.pop(task_manager.task_scheduler, None)
        task_manager.scheduler = None
        task_manager.started = False
        self.addCleanup(
            lambda: task_manager.SingletonMeta._instances.pop(
                task_manager.task_scheduler, None
            )
        )
        self.addCleanup(lambda: setattr(task_manager, "scheduler", None))
        self.addCleanup(lambda: setattr(task_manager, "started", False))

    def test_prepare_enqueues_tasks_without_starting_scheduler_loop(self) -> None:
        render_task = Mock()
        render_task.name = "render"
        render_task.has_run_before = False
        render_task.get_priority_level.return_value = 8

        with (
            patch.object(task_manager, "load_resolution_data", return_value=[]),
            patch.object(task_manager, "load_craft_config", return_value={"generalCraftData": []}),
            patch.object(
                task_manager.stations,
                "render_station",
                return_value=render_task,
                create=True,
            ),
            patch.object(task_manager.task_scheduler, "run") as run,
        ):
            scheduler = task_manager.prepare()

        self.assertIs(task_manager.scheduler, scheduler)
        self.assertFalse(task_manager.started)
        self.assertFalse(scheduler.waiting_queue.is_empty())
        run.assert_not_called()
