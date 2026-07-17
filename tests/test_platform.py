"""Cross-platform plumbing: the bin/afterwit sh-python polyglot launcher and
the fcntl/msvcrt lock helpers in capture.py."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "afterwit" / "src"))

from afterwit import capture  # noqa: E402

BIN = Path(__file__).resolve().parents[1] / "plugins" / "afterwit" / "bin" / "afterwit"


class LauncherTestCase(unittest.TestCase):
    def test_launcher_is_valid_python(self):
        # The sh preamble lives inside a Python string literal — if the
        # polyglot is ever broken, this compiles no more.
        compile(BIN.read_text(encoding="utf-8"), str(BIN), "exec")

    def test_launcher_runs_under_python_directly(self):
        # `python <path>/afterwit` must work where sh doesn't (PowerShell).
        proc = subprocess.run(
            [sys.executable, str(BIN), "--version"],
            capture_output=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("afterwit", proc.stdout)

    @unittest.skipIf(os.name == "nt", "sh execution is POSIX/Git Bash only")
    def test_launcher_runs_via_sh(self):
        proc = subprocess.run(
            ["sh", str(BIN), "--version"],
            capture_output=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("afterwit", proc.stdout)


class LockTestCase(unittest.TestCase):
    @unittest.skipIf(capture.fcntl is None and capture.msvcrt is None,
                     "no locking primitive on this platform")
    def test_nonblocking_conflict_detected_and_released(self):
        # flock (per open-file-description) and msvcrt (per handle) both
        # conflict across two opens of the same file, even in one process.
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "test.lock"
            with p.open("a") as fh1, p.open("a") as fh2:
                self.assertTrue(capture.lock_file(fh1, blocking=False))
                self.assertFalse(capture.lock_file(fh2, blocking=False))
                capture.unlock_file(fh1)
                self.assertTrue(capture.lock_file(fh2, blocking=False))
                capture.unlock_file(fh2)

    def test_unlock_never_raises_on_unlocked_handle(self):
        with tempfile.TemporaryDirectory() as d:
            with (Path(d) / "x.lock").open("a") as fh:
                capture.unlock_file(fh)  # must be a silent no-op


if __name__ == "__main__":
    unittest.main()
