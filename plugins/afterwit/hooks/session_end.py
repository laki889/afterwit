#!/usr/bin/env python3
"""SessionEnd hook — enqueue the finished session for later distillation.

Contract (spec section 5.1): instant, non-blocking, idempotent, NO LLM call,
and it must never disturb the session — every failure path exits 0 silently.

Stdin payload (Claude Code hooks reference):
  {session_id, transcript_path, cwd, hook_event_name: "SessionEnd", why}
where `why` is one of: clear | resume | logout | prompt_input_exit |
bypass_permissions_disabled | other.
"""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)


def main() -> None:
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict):
        return
    session_id = payload.get("session_id")
    transcript_path = payload.get("transcript_path")
    if not session_id or not transcript_path:
        return

    from afterwit import capture, paths

    cwd = payload.get("cwd") or ""
    capture.enqueue(
        {
            "session_id": session_id,
            "transcript_path": transcript_path,
            "cwd": cwd,
            "project": paths.project_name_from_cwd(cwd),
            # docs call this field `why`; accept older `reason` just in case
            "why": payload.get("why") or payload.get("reason") or "",
            "enqueued_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # a capture failure must never surface into the session
    sys.exit(0)
