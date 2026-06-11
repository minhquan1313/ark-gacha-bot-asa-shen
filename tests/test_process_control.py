import subprocess
import unittest
from unittest.mock import Mock, patch

from source.launcher.process_control import (
    poll_kill_after_deadline,
    terminate_process_tree,
)


class ProcessControlTests(unittest.TestCase):
    def test_direct_fallback_terminates_before_kill(self):
        process = Mock()
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("cmd", 1), None]

        with patch.dict("sys.modules", {"psutil": None}):
            terminate_process_tree(process, terminate_timeout=1, kill_timeout=1)

        process.terminate.assert_called_once_with()
        process.kill.assert_called_once_with()

    def test_process_tree_uses_psutil_children_before_parent(self):
        child = Mock()
        parent = Mock()
        parent.children.return_value = [child]
        psutil = Mock()
        psutil.Process.return_value = parent
        psutil.wait_procs.return_value = ([child, parent], [])

        process = Mock()
        process.pid = 123
        process.poll.return_value = None

        with patch.dict("sys.modules", {"psutil": psutil}):
            terminate_process_tree(process)

        child.terminate.assert_called_once_with()
        parent.terminate.assert_called_once_with()
        psutil.wait_procs.assert_called_once()

    def test_poll_kill_after_deadline_kills_running_process(self):
        process = Mock()
        process.poll.return_value = None

        self.assertTrue(poll_kill_after_deadline(process, 0))
        process.kill.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
