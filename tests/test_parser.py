"""Parser tests against a fixture that mirrors the real transcript format
(verified by inspecting 60 transcripts from Claude Code 2.1.138–2.1.207),
including its trickiest property: one logical assistant message split across
multiple JSONL lines that share message.id, with tool-result user lines
INTERLEAVED between the chunks (parallel tool calls)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "afterwit" / "src"))

from afterwit import parser  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "sample_transcript.jsonl"


class ParserTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = parser.parse_file(FIXTURE)

    def test_message_id_grouping_collapses_streamed_chunks(self):
        """4 JSONL lines share msg_AAA (thinking, text, tool_use, tool_use)
        and must merge into ONE logical message — even though tool_result
        user lines are interleaved between the 3rd and 4th chunk."""
        msg_a = [m for m in self.t.messages if m.message_id == "msg_AAA"]
        self.assertEqual(len(msg_a), 1)
        self.assertEqual(
            [b["type"] for b in msg_a[0].blocks],
            ["thinking", "text", "tool_use", "tool_use"],
        )

    def test_logical_message_sequence(self):
        """Roles in order, with meta/sidechain/api-error/non-message lines
        gone and streamed chunks merged."""
        roles = [m.role for m in self.t.messages]
        self.assertEqual(
            roles,
            [
                "user",       # initial prompt
                "assistant",  # msg_AAA (merged from 4 lines)
                "user",       # tool_result for toolu_001
                "user",       # tool_result for toolu_002
                "assistant",  # msg_BBB diagnosis
                "user",       # follow-up (array text content)
                "assistant",  # msg_CCC fix confirmation
            ],
        )

    def test_naive_line_count_would_be_wrong(self):
        """The fixture has 8 non-sidechain assistant JSONL lines (one is an
        API-error placeholder); the correct logical count is 3."""
        assistants = [m for m in self.t.messages if m.role == "assistant"]
        self.assertEqual(len(assistants), 3)

    def test_meta_lines_excluded(self):
        for m in self.t.messages:
            for b in m.blocks:
                self.assertNotIn("local-command-caveat", b.get("text", ""))

    def test_sidechain_excluded_by_default_included_on_request(self):
        ids = [m.message_id for m in self.t.messages]
        self.assertNotIn("msg_SIDE", ids)
        t2 = parser.parse_file(FIXTURE, include_sidechain=True)
        self.assertIn("msg_SIDE", [m.message_id for m in t2.messages])

    def test_api_error_placeholder_excluded(self):
        ids = [m.message_id for m in self.t.messages]
        self.assertNotIn("msg_ERR", ids)

    def test_session_metadata(self):
        self.assertEqual(self.t.session_id, "11111111-2222-3333-4444-555555555555")
        self.assertEqual(self.t.cwd, "/Users/dev/projects/acme-app")
        self.assertEqual(self.t.project, "acme-app")
        self.assertEqual(self.t.git_branch, "main")
        self.assertEqual(self.t.version, "2.1.207")
        self.assertEqual(self.t.first_ts, "2026-07-10T14:00:01.000Z")
        self.assertEqual(self.t.last_ts, "2026-07-10T14:01:30.000Z")

    def test_corrupt_and_truncated_lines_tolerated(self):
        # one corrupt line + one truncated final line (live-appended file)
        self.assertEqual(self.t.skipped_lines, 2)

    def test_tool_result_string_and_array_content(self):
        results = [
            b
            for m in self.t.messages
            for b in m.blocks
            if b.get("type") == "tool_result"
        ]
        self.assertEqual(len(results), 2)
        texts = [parser._tool_result_text(b) for b in results]
        self.assertIn("Connection refused", texts[0])   # string content
        self.assertIn("EADDRINUSE", texts[1])           # array-of-blocks content

    def test_render_transcript(self):
        text = parser.render_transcript(self.t)
        self.assertIn("## USER", text)
        self.assertIn("## ASSISTANT", text)
        self.assertIn("[tool call] Bash", text)
        self.assertIn("[tool result] ERROR", text)      # is_error surfaced
        self.assertIn("zombie process", text)           # diagnosis text kept
        # thinking blocks and harness noise never reach the rendering
        self.assertNotIn("Private reasoning", text)
        self.assertNotIn("local-command-caveat", text)
        self.assertNotIn("Sidechain content", text)
        self.assertNotIn("API Error: overloaded", text)

    def test_render_budget_drops_middle_not_ends(self):
        big = parser.Transcript(
            messages=[
                parser.Message(role="user", blocks=[{"type": "text", "text": f"message number {i} " + "x" * 200}])
                for i in range(50)
            ]
        )
        out = parser.render_transcript(big, max_chars=3000)
        self.assertLess(len(out), 3000 + 500)
        self.assertIn("message number 0", out)    # head kept
        self.assertIn("message number 49", out)   # tail kept
        self.assertIn("omitted for length", out)  # explicit marker

    def test_empty_input(self):
        t = parser.parse_lines([])
        self.assertEqual(t.messages, [])
        self.assertEqual(parser.render_transcript(t), "")


if __name__ == "__main__":
    unittest.main()
