import copy
import json
from pathlib import Path
import tempfile
import unittest

from verify_results import verify


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root / "benchmark"
        self.run.mkdir()
        self.payload = {
            "run_rows": [dict(seed=s, households=1000, ticks_requested=80, ticks_completed=80,
                              failed=False, error="") for s in (42, 43, 44)],
            "tick_rows": [{} for _ in range(240)],
        }
        for name in ("tick_rows.csv", "run_rows.csv", "summary.md"):
            (self.run / name).write_text("fixture\n")

    def write(self):
        (self.run / "raw.json").write_text(json.dumps(self.payload))

    def test_complete(self):
        self.write()
        self.assertEqual(verify(self.root)["total_ticks"], 240)

    def test_failed_and_incomplete_runs(self):
        original = copy.deepcopy(self.payload)
        for key, value in (("failed", True), ("error", "failure"), ("ticks_completed", 79),
                           ("households", 100), ("seed", 99)):
            with self.subTest(key=key):
                self.payload = copy.deepcopy(original)
                self.payload["run_rows"][0][key] = value
                self.write()
                with self.assertRaises(ValueError):
                    verify(self.root)

    def test_missing_tick_and_artifact(self):
        self.payload["tick_rows"].pop()
        self.write()
        with self.assertRaises(ValueError):
            verify(self.root)
        self.payload["tick_rows"].append({})
        self.write()
        (self.run / "summary.md").unlink()
        with self.assertRaises(ValueError):
            verify(self.root)

    def test_extra_benchmark_rejected(self):
        self.write()
        extra = self.root / "extra"
        extra.mkdir()
        (extra / "raw.json").write_text("{}")
        with self.assertRaises(ValueError):
            verify(self.root)


if __name__ == "__main__":
    unittest.main()
