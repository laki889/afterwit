"""Data-directory resolution.

The lessons database, queue, and config live OUTSIDE the plugin directory so
that `/plugin update` and uninstall can never wipe user data.

Resolution order:
  1. $AFTERWIT_DATA_DIR            (explicit override; also used by tests)
  2. $XDG_DATA_HOME/afterwit       (if XDG_DATA_HOME is set)
  3. %LOCALAPPDATA%/afterwit       (Windows)
  4. ~/.local/share/afterwit       (macOS / Linux default)
  5. ~/.claude/afterwit            (last-resort fallback)
"""

from __future__ import annotations

import os
from pathlib import Path


def data_dir(create: bool = True) -> Path:
    """Return the afterwit data directory, creating it if requested."""
    override = os.environ.get("AFTERWIT_DATA_DIR")
    if override:
        d = Path(override).expanduser()
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        if xdg:
            d = Path(xdg).expanduser() / "afterwit"
        elif os.name == "nt" and os.environ.get("LOCALAPPDATA"):
            d = Path(os.environ["LOCALAPPDATA"]) / "afterwit"
        else:
            d = Path.home() / ".local" / "share" / "afterwit"
    if create:
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError:
            d = Path.home() / ".claude" / "afterwit"
            d.mkdir(parents=True, exist_ok=True)
    return d


def db_path() -> Path:
    return data_dir() / "afterwit.db"


def queue_path() -> Path:
    return data_dir() / "queue.jsonl"


def config_path() -> Path:
    return data_dir() / "config.json"


def log_path() -> Path:
    return data_dir() / "afterwit.log"


def claude_projects_dir() -> Path:
    """Claude Code's own transcript store (read-only for us). Resolution:
      1. $AFTERWIT_CLAUDE_DIR/projects   (explicit override; also used by tests)
      2. $CLAUDE_CONFIG_DIR/projects     (the host's own config-dir override)
      3. ~/.claude/projects              (default)
    """
    override = os.environ.get("AFTERWIT_CLAUDE_DIR")
    if override:
        return Path(override).expanduser() / "projects"
    cfg = os.environ.get("CLAUDE_CONFIG_DIR")
    if cfg:
        return Path(cfg).expanduser() / "projects"
    return Path.home() / ".claude" / "projects"


def project_name_from_cwd(cwd: str) -> str:
    """Derive a human-readable project name from a session's cwd."""
    if not cwd:
        return "unknown"
    return Path(cwd).name or "unknown"
