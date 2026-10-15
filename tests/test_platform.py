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


HOOKS_DIR = Path(__file__).resolve().parents[1] / "plugins" / "afterwit" / "hooks"
PLUGIN_ROOT = HOOKS_DIR.parent
FIXTURE = Path(__file__).parent / "fixtures" / "sample_transcript.jsonl"


class HookLauncherTestCase(unittest.TestCase):
    """hooks.json must point at plain shell launchers by literal
    ${CLAUDE_PLUGIN_ROOT} paths — the directory validator refuses inline
    programs (`python3 -c ""`) and computed paths in hook commands — and the
    launchers must actually run the Python hooks."""

    def test_hook_commands_are_literal_launcher_paths(self):
        import json
        import re
        spec = json.loads((HOOKS_DIR / "hooks.json").read_text(encoding="utf-8"))
        commands = [
            h["command"]
            for event in spec["hooks"].values()
            for group in event
            for h in group["hooks"]
        ]
        self.assertEqual(len(commands), 2)
        for cmd in commands:
            self.assertRegex(cmd, r'^"\$\{CLAUDE_PLUGIN_ROOT\}/hooks/session_(end|start)\.sh"$')
            self.assertNotIn(" -c ", cmd)
            script = HOOKS_DIR / cmd.split("/hooks/")[1].rstrip('"')
            self.assertTrue(script.exists(), script)
            text = script.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("#!/bin/sh\n"))
            code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
            self.assertNotIn(" -c ", code)           # no inline programs
            self.assertNotIn("$(", code)             # no command substitution
            self.assertNotIn("$0", code)
            self.assertNotIn("$@", code)

    def _run_launcher(self, name, payload, data_dir):
        env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT),
               "AFTERWIT_DATA_DIR": data_dir}
        env.pop("AFTERWIT_SYNC", None)
        return subprocess.run(
            ["sh", str(HOOKS_DIR / name)], input=payload, capture_output=True,
            encoding="utf-8", timeout=60, env=env,
        )

    @unittest.skipIf(os.name == "nt", "sh execution is POSIX/Git Bash only")
    def test_session_end_launcher_enqueues(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            payload = json.dumps({
                "session_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "transcript_path": str(FIXTURE),
                "cwd": "/Users/dev/projects/acme-app",
                "hook_event_name": "SessionEnd", "why": "other",
            })
            proc = self._run_launcher("session_end.sh", payload, d)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            queue = (Path(d) / "queue.jsonl").read_text(encoding="utf-8")
            self.assertIn("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", queue)

    @unittest.skipIf(os.name == "nt", "sh execution is POSIX/Git Bash only")
    def test_session_start_launcher_is_silent_without_a_database(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            payload = json.dumps({"session_id": "x", "cwd": d,
                                  "hook_event_name": "SessionStart", "source": "startup"})
            proc = self._run_launcher("session_start.sh", payload, d)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
