"""Lesson synthesis — the extraction prompt, the inference backends, and
robust parsing of the model's output.

Network policy (hard constraint): the ONLY egress in this package is the
inference call itself, to the user's own `claude` CLI (their existing
account) or to a LOCAL Ollama server. The Ollama URL is validated to be
loopback; anything else is refused.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

EXTRACTION_PROMPT = """You are analyzing the transcript of one Claude Code development session (provided as input). Extract only genuinely REUSABLE lessons: recurring mistakes, non-obvious gotchas, root causes of real problems, corrected misconceptions, and good decisions worth repeating — things that would change how this developer (or their AI assistant) works in FUTURE sessions.

Rules:
- Quality over quantity. Most sessions contain 0-3 real lessons. If nothing generalizes, return [].
- IGNORE: typos, one-off syntax slips, transient environment noise, routine lookups, generic best practices any developer already knows, and project trivia that will never recur.
- Name the PATTERN, not the incident. Good: "N+1 query from lazy-loading inside a loop". Bad: "had a database issue".
- Each lesson must be self-contained: understandable months from now without this transcript.
- problem: the concrete situation that occurred in this session (1-2 sentences).
- root_cause: the underlying WHY (wrong assumption, missing knowledge, tool quirk, design flaw) — not a restatement of the problem.
- resolution: what actually fixed or settled it in this session.
- lesson: the generalizable, actionable takeaway, phrased as guidance: "When X, do Y, because Z."
- tags: 1-4 short lowercase topic tags (e.g. "sqlite", "async", "deploy", "chrome-extension", "testing").
- confidence: your 0-1 estimate that this is real, reusable, and worth resurfacing later. Use < 0.5 for anything speculative.
- NEVER include secrets, API keys, tokens, passwords, or personal data in any field. Refer to them generically ("the API key") if relevant.
- Do NOT duplicate or near-duplicate any of these already-recorded lessons:
{known_titles}

Output STRICT JSON only — a single array, no prose, no markdown fences:
[{{"title": "...", "problem": "...", "root_cause": "...", "resolution": "...", "lesson": "...", "tags": ["..."], "confidence": 0.8}}]"""


def build_prompt(known_titles: list[str]) -> str:
    titles = "\n".join(f"  - {t}" for t in known_titles[:60]) or "  (none yet)"
    return EXTRACTION_PROMPT.format(known_titles=titles)


class BackendError(Exception):
    """Inference failed for this session in a way worth retrying later."""


class BackendUnavailable(BackendError):
    """The backend itself is unusable (missing binary, auth expired, server
    down) — the whole sync run should abort WITHOUT charging retry attempts,
    since every session would fail identically (think: cron job on a box
    where `claude` isn't on PATH)."""


# ---------------------------------------------------------------------------
# Backend: the user's own `claude` CLI (default)

def _scrubbed_env() -> dict[str, str]:
    """Environment for the nested `claude -p` call: drop the variables that
    mark 'running inside a Claude Code session' (they confuse a nested CLI),
    and set AFTERWIT_SYNC so our own SessionEnd hook ignores the run."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT")
    }
    env["AFTERWIT_SYNC"] = "1"
    return env


def call_claude(prompt: str, transcript_text: str, cfg: dict[str, Any]) -> str:
    """Run `claude -p` headless with all tools disabled and return the model's
    text. Uses the user's existing CLI auth — no new credentials, no new party.
    Prompt AND transcript both go via stdin so nothing appears in process argv
    (visible to `ps`)."""
    binary = os.environ.get("AFTERWIT_CLAUDE_BIN", "claude")
    cmd = [
        binary, "-p",
        "--tools", "",
        "--output-format", "json",
        "--no-session-persistence",
    ]
    if cfg.get("claude_model"):
        cmd += ["--model", str(cfg["claude_model"])]
    stdin_payload = f"{prompt}\n\n--- SESSION TRANSCRIPT ---\n{transcript_text}"
    try:
        proc = subprocess.run(
            cmd,
            input=stdin_payload,
            capture_output=True,
            text=True,
            timeout=int(cfg.get("claude_timeout", 600)),
            env=_scrubbed_env(),
        )
    except FileNotFoundError:
        raise BackendUnavailable(
            f"`{binary}` not found on PATH. Install Claude Code, set AFTERWIT_CLAUDE_BIN, "
            "or (for cron/launchd) put its directory on PATH in the job definition."
        )
    except subprocess.TimeoutExpired:
        raise BackendError("claude -p timed out")
    if proc.returncode != 0:
        raise BackendError(
            f"claude -p exited {proc.returncode}: {(proc.stderr or proc.stdout)[:300]}"
        )
    # --output-format json wraps the reply in an envelope: {"type":"result",
    # "subtype":"success","is_error":false,"result":"<text>",...}
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.stdout  # older CLI / plain text — let the parser try
    if not isinstance(envelope, dict):
        return proc.stdout
    if envelope.get("is_error") or envelope.get("subtype") != "success":
        detail = str(envelope.get("result"))[:300]
        if "authenticate" in detail.lower() or "log in" in detail.lower():
            raise BackendUnavailable(
                f"claude CLI is not authenticated ({detail}). Run `claude auth login`."
            )
        raise BackendError(f"claude -p error: {detail}")
    result = envelope.get("result")
    return result if isinstance(result, str) else json.dumps(result)


# ---------------------------------------------------------------------------
# Backend: local Ollama (max privacy — nothing reaches Anthropic)

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]"}


def call_ollama(prompt: str, transcript_text: str, cfg: dict[str, Any]) -> str:
    base = str(cfg.get("ollama_url", "http://localhost:11434")).rstrip("/")
    host = urllib.parse.urlparse(base).hostname or ""
    if host not in _LOOPBACK_HOSTS:
        raise BackendError(
            f"ollama_url host '{host}' is not loopback. Afterwit only talks to a "
            "LOCAL Ollama server — refusing to send data anywhere else."
        )
    body = json.dumps(
        {
            "model": cfg.get("ollama_model", "llama3.1"),
            "stream": False,
            "messages": [
                {"role": "user", "content": f"{prompt}\n\n--- SESSION TRANSCRIPT ---\n{transcript_text}"}
            ],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/api/chat", data=body, headers={"Content-Type": "application/json"}
    )
    # ProxyHandler({}) disables http_proxy/HTTPS_PROXY env vars — without it a
    # configured proxy would receive the transcript, violating "100% local".
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=int(cfg.get("ollama_timeout", 600))) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise BackendUnavailable(
            f"Ollama not reachable at {base} ({e.reason if hasattr(e, 'reason') else e}). "
            "Start it with `ollama serve` and pull a model, or use the claude backend."
        )
    except (json.JSONDecodeError, OSError) as e:
        raise BackendError(f"Ollama returned an unreadable response: {e}")
    message = payload.get("message") or {}
    content = message.get("content", "")
    if not content:
        raise BackendError(f"Ollama returned no content: {str(payload)[:200]}")
    return content


BACKENDS = {"claude": call_claude, "ollama": call_ollama}


# ---------------------------------------------------------------------------
# Output parsing — strict target, forgiving reader, never raises.

_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|```\s*$", re.MULTILINE)


def parse_lessons(text: str) -> tuple[list[dict[str, Any]], str | None]:
    """Parse the model's reply into validated lesson dicts.
    Returns (lessons, error). error is set only when nothing parseable was
    found; an empty list with no error means 'model said no lessons'."""
    if not text or not text.strip():
        return [], "empty model output"
    cleaned = _FENCE_RE.sub("", text.strip()).strip()

    data = _try_json(cleaned)
    if data is None:
        start, end = cleaned.find("["), cleaned.rfind("]")
        if start != -1 and end > start:
            data = _try_json(cleaned[start : end + 1])
    if data is None:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            data = _try_json(cleaned[start : end + 1])
    if isinstance(data, dict):
        if "title" in data and "lesson" in data:
            data = [data]  # a single bare lesson object without the array
        else:
            data = data.get("lessons", data.get("items"))
    if data is None:
        return [], f"no JSON found in model output: {cleaned[:120]!r}"
    if not isinstance(data, list):
        return [], f"model output was not a JSON array: {type(data).__name__}"

    lessons = []
    for item in data:
        lesson = _validate(item)
        if lesson:
            lessons.append(lesson)
    return lessons, None


def _try_json(s: str) -> Any | None:
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return None


def _validate(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    title = str(item.get("title") or "").strip()
    problem = str(item.get("problem") or "").strip()
    lesson = str(item.get("lesson") or "").strip()
    if not title or not lesson:
        return None
    if not problem:
        problem = title
    tags = item.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]
    if not isinstance(tags, list):
        tags = []
    tags = [str(t).strip().lower()[:40] for t in tags if str(t).strip()][:6]
    confidence = item.get("confidence")
    try:
        confidence = max(0.0, min(1.0, float(confidence))) if confidence is not None else None
    except (TypeError, ValueError):
        confidence = None
    return {
        "title": title[:200],
        "problem": problem[:1000],
        "root_cause": str(item.get("root_cause") or "").strip()[:1000] or None,
        "resolution": str(item.get("resolution") or "").strip()[:1000] or None,
        "lesson": lesson[:1000],
        "tags": tags,
        "confidence": confidence,
    }
