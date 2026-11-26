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

# Every variable below is named literally, on purpose: the plugin directory's
# policy check treats a variable whose name is only known at run time as a
# possible credential read.
#
# CLAUDECODE, CLAUDE_CODE_ENTRYPOINT and CLAUDE_CODE_SSE_PORT are set by
# Claude Code inside a session. A nested CLI that inherits them thinks it is
# that same session, so they are hidden for the duration of the call.
# AFTERWIT_SYNC tells afterwit's own SessionEnd hook that the session it sees
# is an extraction run, which must never be captured as a lesson source.


def claude_binary() -> str:
    """Name or path of the `claude` CLI: `AFTERWIT_CLAUDE_BIN` when set (for a
    binary that isn't on PATH, e.g. under cron/launchd), else `claude`."""
    return os.environ.get("AFTERWIT_CLAUDE_BIN") or "claude"


@contextlib.contextmanager
def nested_cli() -> Iterator[None]:
    """Run the body with the session markers hidden and the sync marker set,
    then put those four names back exactly as they were. Nothing else in the
    environment is read or changed."""
    claudecode = os.environ.pop("CLAUDECODE", None)
    entrypoint = os.environ.pop("CLAUDE_CODE_ENTRYPOINT", None)
    sse_port = os.environ.pop("CLAUDE_CODE_SSE_PORT", None)
    was_marked = "AFTERWIT_SYNC" in os.environ
    os.environ["AFTERWIT_SYNC"] = "1"
    try:
        yield
    finally:
        if not was_marked:
            os.environ.pop("AFTERWIT_SYNC", None)
        if claudecode is not None:
            os.environ["CLAUDECODE"] = claudecode
        if entrypoint is not None:
            os.environ["CLAUDE_CODE_ENTRYPOINT"] = entrypoint
        if sse_port is not None:
            os.environ["CLAUDE_CODE_SSE_PORT"] = sse_port
