"""Claude Code transcript (JSONL) parser.

The format is one JSON object per line, but NOT one message per line: a
streamed assistant message is written as several consecutive lines that share
the same `message.id`, each carrying one content block. Naive per-line parsing
yields fragmented/miscounted messages, so we group lines by message id and
merge their content blocks, preserving first-seen order.

Other realities this parser tolerates:
  - blank lines and corrupt/truncated JSON lines (skipped)
  - non-message line types ("summary", "file-history-snapshot", ...)
  - meta lines (isMeta) and sidechain/subagent lines (isSidechain)
  - user `message.content` as either a plain string or a block array
    (text / tool_result blocks)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass
class Message:
    """One logical conversation message (streaming chunks already merged)."""

    role: str                       # "user" | "assistant"
    blocks: list[dict[str, Any]] = field(default_factory=list)
    message_id: str | None = None   # assistant messages only
    timestamp: str | None = None    # ISO8601 of the first line
    uuid: str | None = None


@dataclass
class Transcript:
    session_id: str | None = None
    cwd: str | None = None
    git_branch: str | None = None
    version: str | None = None
    first_ts: str | None = None
    last_ts: str | None = None
    messages: list[Message] = field(default_factory=list)
    skipped_lines: int = 0          # unparseable lines (diagnostics only)

    @property
    def project(self) -> str | None:
        if not self.cwd:
            return None
        return Path(self.cwd).name or None


def parse_file(path: str | Path, include_sidechain: bool = False) -> Transcript:
    p = Path(path)
    with p.open("r", encoding="utf-8", errors="replace") as f:
        return parse_lines(f, include_sidechain=include_sidechain)


def parse_lines(lines: Iterable[str], include_sidechain: bool = False) -> Transcript:
    t = Transcript()
    # message.id -> Message, so streamed assistant chunks merge into one
    # logical message even if another line lands between them.
    by_msg_id: dict[str, Message] = {}

    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            t.skipped_lines += 1
            continue
        if not isinstance(rec, dict):
            t.skipped_lines += 1
            continue

        rec_type = rec.get("type")
        if rec_type not in ("user", "assistant"):
            continue  # summary / file-history-snapshot / system / attachment / unknown
        if rec.get("isSidechain") and not include_sidechain:
            continue
        if rec.get("isMeta"):
            continue  # injected context, command echoes, etc.
        if rec.get("isApiErrorMessage"):
            continue  # synthetic assistant record holding an API error string

        # Session metadata: take the first value seen; track last timestamp.
        ts = rec.get("timestamp")
        t.session_id = t.session_id or rec.get("sessionId")
        t.cwd = t.cwd or rec.get("cwd")
        t.git_branch = t.git_branch or rec.get("gitBranch")
        t.version = t.version or rec.get("version")
        if ts:
            t.first_ts = t.first_ts or ts
            t.last_ts = ts

        msg = rec.get("message")
        if not isinstance(msg, dict):
            continue
        blocks = _content_blocks(msg.get("content"))

        if rec_type == "assistant":
            msg_id = msg.get("id")
            if msg_id and msg_id in by_msg_id:
                by_msg_id[msg_id].blocks.extend(blocks)  # streamed chunk
                continue
            m = Message(
                role="assistant",
                blocks=blocks,
                message_id=msg_id,
                timestamp=ts,
                uuid=rec.get("uuid"),
            )
            if msg_id:
                by_msg_id[msg_id] = m
            t.messages.append(m)
        else:
            t.messages.append(
                Message(role="user", blocks=blocks, timestamp=ts, uuid=rec.get("uuid"))
            )

    return t


def _content_blocks(content: Any) -> list[dict[str, Any]]:
    """Normalize message.content (string | block array) to a block list."""
    if isinstance(content, str):
        return [{"type": "text", "text": content}] if content.strip() else []
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    return []


# ---------------------------------------------------------------------------
# Rendering — a clean text view of the conversation for the extraction LLM.

_TOOL_INPUT_CHARS = 300     # tool call inputs are context, not content
_TOOL_RESULT_CHARS = 700    # results carry error messages — keep more
_TEXT_CHARS = 4000          # per text block


def _clip(s: str, limit: int) -> str:
    s = s.strip()
    if len(s) <= limit:
        return s
    return s[:limit] + f" …[+{len(s) - limit} chars]"


def _tool_result_text(block: dict[str, Any]) -> str:
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        return "\n".join(p for p in parts if p)
    return ""


# Harness-injected wrappers that appear as user text but aren't the user
# speaking; they add noise without lesson value.
_NOISE_PREFIXES = (
    "<command-name>",
    "<local-command-stdout>",
    "<local-command-caveat>",
    "<system-reminder>",
    "[Request interrupted by user",
    "Caveat: The messages below were generated by the user while running",
)


def render_message(m: Message) -> str:
    parts: list[str] = []
    for b in m.blocks:
        btype = b.get("type")
        if btype == "text":
            text = b.get("text", "").strip()
            if text.startswith(_NOISE_PREFIXES):
                continue
            if text:
                parts.append(_clip(text, _TEXT_CHARS))
        elif btype == "tool_use":
            name = b.get("name", "?")
            try:
                arg = json.dumps(b.get("input", {}), ensure_ascii=False)
            except (TypeError, ValueError):
                arg = "{}"
            parts.append(f"[tool call] {name} {_clip(arg, _TOOL_INPUT_CHARS)}")
        elif btype == "tool_result":
            text = _tool_result_text(b)
            status = "ERROR " if b.get("is_error") else ""
            if text.strip():
                parts.append(f"[tool result] {status}{_clip(text, _TOOL_RESULT_CHARS)}")
            elif status:
                parts.append("[tool result] ERROR (no output)")
        # thinking blocks are intentionally skipped: internal, token-heavy
    return "\n".join(parts)


def render_transcript(t: Transcript, max_chars: int = 200_000) -> str:
    """Human/LLM-readable rendering. If over budget, drop whole messages from
    the MIDDLE (beginning sets up the task; the end holds resolutions)."""
    rendered: list[str] = []
    for m in t.messages:
        body = render_message(m)
        if not body:
            continue
        label = "USER" if m.role == "user" else "ASSISTANT"
        rendered.append(f"## {label}\n{body}")

    total = sum(len(r) + 2 for r in rendered)
    if total > max_chars and len(rendered) > 4:
        keep_head = max(2, len(rendered) // 5)
        head, tail = rendered[:keep_head], rendered[keep_head:]
        dropped = 0
        while tail and total > max_chars:
            removed = tail.pop(0)  # drop from the middle, oldest first
            total -= len(removed) + 2
            dropped += 1
        rendered = head + [f"…[{dropped} messages omitted for length]…"] + tail
    return "\n\n".join(rendered)
