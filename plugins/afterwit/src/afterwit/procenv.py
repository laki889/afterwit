"""The two environment touch-points of the nested `claude -p` call.

Afterwit never reads, copies, stores or forwards a credential. The `claude`
CLI is started as an ordinary child process and signs itself in exactly as it
does when the user runs it by hand. The child inherits the environment the
normal way; this module never builds an environment for it and never looks at
any variable's value except the four named below, none of which is a secret.
"""

from __future__ import annotations

import contextlib
import os
from typing import Iterator

# Set by Claude Code inside a session. A nested CLI that inherits them thinks
# it is that same session, so they are hidden for the duration of the call.
_SESSION_MARKERS = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT")

# Tells afterwit's own SessionEnd hook that the session it sees is an
# extraction run, which must never be captured as a lesson source.
_SYNC_MARKER = "AFTERWIT_SYNC"


def claude_binary() -> str:
    """Name or path of the `claude` CLI: `AFTERWIT_CLAUDE_BIN` when set (for a
    binary that isn't on PATH, e.g. under cron/launchd), else `claude`."""
    return os.environ.get("AFTERWIT_CLAUDE_BIN") or "claude"


@contextlib.contextmanager
def nested_cli() -> Iterator[None]:
    """Run the body with the session markers hidden and the sync marker set,
    then put those four names back exactly as they were. Nothing else in the
    environment is read or changed."""
    hidden = {}
    for name in _SESSION_MARKERS:
        if name in os.environ:
            hidden[name] = os.environ[name]
            del os.environ[name]
    was_marked = _SYNC_MARKER in os.environ
    os.environ[_SYNC_MARKER] = "1"
    try:
        yield
    finally:
        if not was_marked:
            del os.environ[_SYNC_MARKER]
        os.environ.update(hidden)
