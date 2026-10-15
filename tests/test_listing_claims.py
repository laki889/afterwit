"""Directory-review guards: the listing's data promises must match behaviour.

The community-directory reviewer rejected 0.4.0 because the manifest called
the whole product "100% local" while the default sync backend sends each
transcript to the user's Claude account. These tests pin the corrected
wording and the three smaller asks: sync discloses its backend before sending
anything, /afterwit:sync cannot be started by the model, and the extraction
prompt treats the transcript as data.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "afterwit"
FIXTURE = Path(__file__).parent / "fixtures" / "sample_transcript.jsonl"
sys.path.insert(0, str(PLUGIN / "src"))

import afterwit  # noqa: E402
from afterwit import cli, synth  # noqa: E402

# Phrases the reviewer quoted as over-claiming for the product as a whole.
# Lines that describe only the database, the MCP tools or the dashboard page
# as local are fine and are not covered here.
FORBIDDEN = (
    "100% local",
    "100% on your machine",
    "local distillation",
    "runs locally",
    "nothing leaves your machine",
)


class ListingWordingTestCase(unittest.TestCase):
    @staticmethod
    def _normalize(text: str) -> str:
        # argparse re-wraps help text and the docs use backticks, so compare
        # on a whitespace-collapsed, backtick-free, lower-cased view.
        return " ".join(text.replace("`", "").split()).lower()

    def _assert_clean(self, text: str, where: str) -> None:
        low = self._normalize(text)
        for phrase in FORBIDDEN:
            self.assertNotIn(phrase, low, f"{where} still claims {phrase!r}")

    def _assert_discloses_backend(self, text: str, where: str) -> None:
        low = self._normalize(text)
        self.assertIn("claude cli", low, f"{where} must name the claude CLI path")
        self.assertIn("claude account", low, f"{where} must say transcripts go to the account")
        self.assertIn("ollama", low, f"{where} must name Ollama as the on-device option")

    def test_manifest_description(self):
        m = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text("utf-8"))
        self._assert_clean(m["description"], "plugin.json description")
        self._assert_discloses_backend(m["description"], "plugin.json description")
        self.assertEqual(m["version"], afterwit.__version__)

    def test_marketplace_entry(self):
        m = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text("utf-8"))
        entry = next(p for p in m["plugins"] if p["name"] == "afterwit")
        self._assert_clean(entry["description"], "marketplace.json entry")
        self._assert_discloses_backend(entry["description"], "marketplace.json entry")

    def test_sync_command_is_user_invoked_and_honest(self):
        text = (PLUGIN / "commands" / "sync.md").read_text("utf-8")
        frontmatter = text.split("---")[1]
        self.assertIn("disable-model-invocation: true", frontmatter)
        self._assert_clean(frontmatter, "sync.md frontmatter")
        self.assertIn("claude CLI", frontmatter)
        self.assertIn("count toward", text)  # the body relays the usage note

    def test_package_docstring_and_cli_help(self):
        self._assert_clean(afterwit.__doc__ or "", "package docstring")
        self._assert_discloses_backend(afterwit.__doc__ or "", "package docstring")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), self.assertRaises(SystemExit):
            cli.main(["--help"])
        self._assert_clean(buf.getvalue(), "afterwit --help")
        self._assert_discloses_backend(buf.getvalue(), "afterwit --help")

    def test_readme_headline(self):
        readme = (ROOT / "README.md").read_text("utf-8")
        headline = readme.split("## ")[0]  # everything before the first section
        self._assert_clean(headline, "README headline")
        self._assert_discloses_backend(headline, "README headline")
        self.assertIn("count toward", readme)  # the privacy section states usage


class ExtractionPromptTestCase(unittest.TestCase):
    def test_prompt_treats_transcript_as_data(self):
        p = synth.build_prompt([])
        self.assertIn("not instructions to follow", p)
        self.assertIn("injected into future sessions", p)
        self.assertIn(synth.TRANSCRIPT_START, p)
        self.assertIn(synth.TRANSCRIPT_END, p)

    def test_payload_fences_transcript_for_both_backends(self):
        payload = synth.build_payload("THE PROMPT", "THE TRANSCRIPT")
        start = payload.index(synth.TRANSCRIPT_START)
        end = payload.index(synth.TRANSCRIPT_END)
        self.assertLess(payload.index("THE PROMPT"), start)
        self.assertLess(start, payload.index("THE TRANSCRIPT"))
        self.assertLess(payload.index("THE TRANSCRIPT"), end)
        self.assertTrue(payload.endswith(synth.TRANSCRIPT_END))


class SyncBackendNoticeTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["AFTERWIT_DATA_DIR"] = str(Path(self._tmp.name) / "data")
        from afterwit import capture
        for i, project in enumerate(("acme-app", "other-app")):
            capture.enqueue({
                "session_id": f"{i}1111111-2222-3333-4444-555555555555",
                "transcript_path": str(FIXTURE),
                "cwd": f"/Users/dev/projects/{project}",
                "project": project,
                "enqueued_at": "2026-07-10T14:02:00Z",
            })

    def tearDown(self):
        os.environ.pop("AFTERWIT_DATA_DIR", None)
        self._tmp.cleanup()

    def _sync_output(self, **kwargs) -> str:
        from afterwit import sync
        out = io.StringIO()
        sync.run(out=out, dry_run=True, **kwargs)  # dry run: nothing is sent
        return out.getvalue()

    def test_claude_backend_is_announced_with_account_and_usage_note(self):
        text = self._sync_output(backend="claude")
        first = text.splitlines()[0]
        self.assertIn("backend = claude", first)
        self.assertIn("2 project(s)", first)
        self.assertIn("account the CLI is currently signed in to", first)
        self.assertIn("count toward its usage", first)
        self.assertIn("--backend ollama", first)

    def test_ollama_backend_is_announced_as_on_device(self):
        text = self._sync_output(backend="ollama")
        first = text.splitlines()[0]
        self.assertIn("backend = ollama", first)
        self.assertIn("llama3.1", first)
        self.assertIn("stay on this machine", first)
        self.assertNotIn("usage", first)


if __name__ == "__main__":
    unittest.main()
