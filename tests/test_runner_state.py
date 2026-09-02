import io
import json
import unittest
from contextlib import redirect_stdout

from source.utility.runner_state import (
    RUNNER_STATE_PREFIX,
    emit_runner_state,
)


class RunnerStateTests(unittest.TestCase):
    def test_emit_runner_state_writes_flushable_protocol_message(self):
        output = io.StringIO()

        with redirect_stdout(output):
            emit_runner_state("PAUSED")

        line = output.getvalue().strip()
        self.assertTrue(line.startswith(RUNNER_STATE_PREFIX))
        payload = json.loads(line[len(RUNNER_STATE_PREFIX) :])
        self.assertEqual(payload, {"state": "PAUSED"})


if __name__ == "__main__":
    unittest.main()
