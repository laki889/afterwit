"""User configuration — config.json in the data dir, with safe defaults.

Every value has a default so the plugin works with zero manual setup.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from . import paths

DEFAULTS: dict[str, Any] = {
    # Inference backend for `afterwit sync`: "claude" (the user's own claude
    # CLI) or "ollama" (fully local; nothing reaches Anthropic).
    "backend": "claude",
    "claude_model": None,          # None → the CLI's default model
    "ollama_url": "http://localhost:11434",
    "ollama_model": "llama3.1",
    # SessionStart injection
    "inject_enabled": True,
    "inject_count": 4,             # lessons per session start
    "inject_min_confidence": 0.0,
    # Synthesis
    "min_confidence": 0.3,         # discard lessons the model itself doubts
    "max_transcript_chars": 200_000,  # truncate huge sessions before distilling
    "claude_timeout": 600,         # seconds per claude -p call
    "ollama_timeout": 600,         # seconds per Ollama call
}


def load(warn: bool = False) -> dict[str, Any]:
    """Load config with defaults. Hooks call this with warn=False (nothing may
    disturb a session); CLI entry points pass warn=True so a broken config —
    which would silently fall back to defaults, e.g. ignoring a configured
    ollama backend — is surfaced on stderr instead of being swallowed."""
    cfg = dict(DEFAULTS)
    p = paths.config_path()
    try:
        if p.exists():
            user = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(user, dict):
                cfg.update(user)
            elif warn:
                print(f"afterwit: {p} is not a JSON object — using defaults.", file=sys.stderr)
    except json.JSONDecodeError as e:
        if warn:
            print(
                f"afterwit: {p} is invalid JSON ({e}) — using defaults. "
                "Note: JSON does not allow // comments.",
                file=sys.stderr,
            )
    except OSError:
        pass  # unreadable config must never break capture/injection
    return cfg


def save(cfg: dict[str, Any]) -> None:
    p = paths.config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    # Persist only non-default keys so defaults can evolve with the plugin.
    delta = {k: v for k, v in cfg.items() if DEFAULTS.get(k, object()) != v}
    p.write_text(json.dumps(delta, indent=2) + "\n", encoding="utf-8")
