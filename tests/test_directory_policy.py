"""Directory-policy guards: what the plugin ships and how it treats the
environment.

The community directory's automatic policy check refused 0.4.1 for three
reasons, and these tests pin the fix for each:

- "Ships executable files": a `bin/` directory (or any compiled program) is
  refused unless the publisher is a Verified organization. The CLI launcher
  now lives in `scripts/`.
- "Uses a credential from the user's machine": synth.py copied the whole
  environment into a dict and handed it to the `claude` subprocess. No code
  may read the environment wholesale or build an env for a child process.
- "Plugin not fully checked": the MCP server command carried a variable the
  validator could not read through. Hook and MCP commands must be literal.
"""

import json
import os
import re
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "afterwit"
sys.path.insert(0, str(PLUGIN / "src"))

from afterwit import procenv, synth  # noqa: E402


def _plugin_files():
    return [
        p for p in PLUGIN.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    ]


class ShippedFilesTestCase(unittest.TestCase):
    def test_no_bin_directory(self):
        self.assertFalse((PLUGIN / "bin").exists(),
                         "the directory refuses a plugin that ships bin/")

    def test_manifest_declares_no_binaries(self):
        manifest = json.loads(
            (PLUGIN / ".claude-plugin" / "plugin.json").read_text("utf-8"))
        self.assertNotIn("binaries", manifest)

    def test_every_shipped_file_is_readable_text(self):
        # No compiled programs, archives or other blobs: everything the
        # plugin runs must be source a reviewer can read.
        for path in _plugin_files():
            if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
                continue
            data = path.read_bytes()
            self.assertNotIn(b"\x00", data, f"{path} looks binary")
            data.decode("utf-8")  # raises on a non-text file

    def test_plugin_root_paths_in_components_exist(self):
        # Every "${CLAUDE_PLUGIN_ROOT}/<file>" a command, skill, hook or MCP
        # entry names must be a file that ships.
        ref = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+)")
        sources = [
            *PLUGIN.glob("commands/*.md"),
            *PLUGIN.glob("skills/*/SKILL.md"),
            *PLUGIN.glob("hooks/*"),
            PLUGIN / ".mcp.json",
        ]
        seen = set()
        for src in sources:
            if not src.is_file() or src.suffix == ".py":
                continue
            for rel in ref.findall(src.read_text(encoding="utf-8")):
                seen.add(rel)
                self.assertTrue((PLUGIN / rel).is_file(), f"{src.name}: {rel} missing")
        self.assertIn("scripts/afterwit.sh", seen)
        self.assertIn("mcp/query_lessons.py", seen)


class CommandShapeTestCase(unittest.TestCase):
    def test_mcp_server_command_is_literal(self):
        spec = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))
        servers = spec["mcpServers"]
        self.assertTrue(servers)
        for name, server in servers.items():
            # a plain program name: no variable, no shell, no path
            self.assertRegex(server["command"], r"^[A-Za-z0-9_.-]+$", name)
            self.assertNotIn(server["command"], ("sh", "bash", "npx", "uvx"), name)
            for arg in server.get("args", []):
                self.assertTrue(arg.startswith("${CLAUDE_PLUGIN_ROOT}/"), arg)
                self.assertEqual(arg.count("${"), 1, arg)
                self.assertNotIn("..", arg)
            self.assertNotIn("env", server, f"{name} must not forward environment")


class EnvironmentHandlingTestCase(unittest.TestCase):
    """The plugin never reads the environment wholesale and never builds one
    for a child process — the pattern the policy check reads as forwarding
    whatever credentials happen to be set."""

    WHOLESALE = (
        "os.environ.items(", "os.environ.copy(", "os.environ.values(",
        "os.environ.keys(", "dict(os.environ", "**os.environ", "environb",
    )

    def test_no_source_file_reads_the_environment_wholesale(self):
        for path in PLUGIN.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for needle in self.WHOLESALE:
                self.assertNotIn(needle, text, f"{path.name} uses {needle}")
            self.assertIsNone(re.search(r"\benv\s*=", text),
                              f"{path.name} passes an env to a child process")

    def test_every_environment_variable_is_named_literally(self):
        # The policy check flags "an environment variable named at run time"
        # (os.environ[name] in a loop) as a possible credential read.
        access = re.compile(r"os\.environ(?:\.get|\.pop|\.setdefault)?\s*[\[(]\s*([^\s])")
        for path in PLUGIN.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for m in access.finditer(text):
                self.assertIn(m.group(1), "\"'",
                              f"{path.name}: non-literal environment key near "
                              f"{text[m.start():m.start() + 40]!r}")
            self.assertNotRegex(text, r"\bin os\.environ\b(?<!\" in os\.environ)",
                                f"{path.name}: membership test on a non-literal name")
            self.assertNotIn("os.getenv(", text)
            self.assertNotIn("os.environ.update(", text)

    def test_synth_does_not_touch_the_environment(self):
        text = (PLUGIN / "src" / "afterwit" / "synth.py").read_text(encoding="utf-8")
        self.assertNotIn("os.environ", text)
        self.assertNotIn("getenv", text)
        self.assertNotRegex(text, r"(?m)^import os$")

    def test_procenv_names_only_non_secret_variables(self):
        text = (PLUGIN / "src" / "afterwit" / "procenv.py").read_text(encoding="utf-8")
        names = set(re.findall(r'"([A-Z][A-Z0-9_]+)"', text))
        self.assertEqual(names, {
            "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT",
            "AFTERWIT_SYNC", "AFTERWIT_CLAUDE_BIN",
        })
        for name in names:
            self.assertNotRegex(name, r"KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH")


def _write_env_stub(dirpath: Path) -> Path:
    """A fake `claude` CLI that reports, as its reply, which of the watched
    variables it can see."""
    stub = dirpath / "env-stub.py"
    stub.write_text(
        "import json,os,sys\n"
        "sys.stdin.read()\n"
        "seen = {k: os.environ.get(k) for k in ('CLAUDECODE',"
        " 'CLAUDE_CODE_ENTRYPOINT', 'CLAUDE_CODE_SSE_PORT', 'AFTERWIT_SYNC',"
        " 'AFTERWIT_TEST_PASSTHROUGH')}\n"
        "print(json.dumps({'type': 'result', 'subtype': 'success',"
        " 'is_error': False, 'result': json.dumps(seen)}))\n",
        encoding="utf-8",
    )
    if os.name == "nt":
        shim = dirpath / "env-stub.cmd"
        shim.write_text(f'@"{sys.executable}" "{stub}" %*\n', encoding="utf-8")
        return shim
    runner = dirpath / "env-stub"
    runner.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{stub}" "$@"\n')
    runner.chmod(runner.stat().st_mode | stat.S_IEXEC)
    return runner


class NestedCliEnvironmentTestCase(unittest.TestCase):
    WATCHED = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT",
               "AFTERWIT_SYNC", "AFTERWIT_CLAUDE_BIN", "AFTERWIT_TEST_PASSTHROUGH")

    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in self.WATCHED}
        for k in self.WATCHED:
            os.environ.pop(k, None)
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._tmp.cleanup()

    def test_child_sees_sync_marker_and_no_session_markers(self):
        os.environ["CLAUDECODE"] = "1"
        os.environ["CLAUDE_CODE_ENTRYPOINT"] = "cli"
        os.environ["CLAUDE_CODE_SSE_PORT"] = "12345"
        os.environ["AFTERWIT_TEST_PASSTHROUGH"] = "inherited"
        os.environ["AFTERWIT_CLAUDE_BIN"] = str(_write_env_stub(Path(self._tmp.name)))

        seen = json.loads(synth.call_claude("p", "t", {}))

        self.assertEqual(seen["AFTERWIT_SYNC"], "1")
        self.assertIsNone(seen["CLAUDECODE"])
        self.assertIsNone(seen["CLAUDE_CODE_ENTRYPOINT"])
        self.assertIsNone(seen["CLAUDE_CODE_SSE_PORT"])
        # ordinary inheritance: nothing was filtered or rebuilt
        self.assertEqual(seen["AFTERWIT_TEST_PASSTHROUGH"], "inherited")

        # ...and this process is left exactly as it was
        self.assertEqual(os.environ["CLAUDECODE"], "1")
        self.assertEqual(os.environ["CLAUDE_CODE_ENTRYPOINT"], "cli")
        self.assertEqual(os.environ["CLAUDE_CODE_SSE_PORT"], "12345")
        self.assertNotIn("AFTERWIT_SYNC", os.environ)

    def test_environment_restored_when_the_call_fails(self):
        os.environ["CLAUDECODE"] = "1"
        os.environ["AFTERWIT_CLAUDE_BIN"] = "/nonexistent/claude-binary"
        with self.assertRaises(synth.BackendUnavailable):
            synth.call_claude("p", "t", {})
        self.assertEqual(os.environ["CLAUDECODE"], "1")
        self.assertNotIn("AFTERWIT_SYNC", os.environ)

    def test_existing_sync_marker_is_kept(self):
        os.environ["AFTERWIT_SYNC"] = "1"
        with procenv.nested_cli():
            self.assertEqual(os.environ["AFTERWIT_SYNC"], "1")
        self.assertEqual(os.environ["AFTERWIT_SYNC"], "1")

    def test_claude_binary_default_and_override(self):
        self.assertEqual(procenv.claude_binary(), "claude")
        os.environ["AFTERWIT_CLAUDE_BIN"] = "/opt/claude/bin/claude"
        self.assertEqual(procenv.claude_binary(), "/opt/claude/bin/claude")


if __name__ == "__main__":
    unittest.main()
