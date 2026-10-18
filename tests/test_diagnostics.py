import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import diagnostics


class DiagnosticsTests(unittest.TestCase):
    def test_abnormal_exit_is_reported_on_next_start(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(diagnostics, "LOG_DIR", Path(directory)):
            diagnostics.mark_run()
            with self.assertLogs(level="WARNING") as logs:
                diagnostics.mark_run()
            self.assertIn("sem encerramento normal", logs.output[0])
            diagnostics.mark_run(clean=True)
            state = json.loads((Path(directory) / "last-run.json").read_text())
            self.assertTrue(state["clean"])


if __name__ == "__main__":
    unittest.main()
