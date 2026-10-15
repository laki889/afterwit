#!/bin/sh
# Launcher for session_end.py — a plain shell script with literal paths so the
# directory validator can follow it (an inline interpreter probe written
# straight into hooks.json is refused as an unreadable inline program).
#
# Probe for a WORKING interpreter, python3 first, then python. `--version`
# rejects the Microsoft-Store alias stub that sits on PATH pretending to be
# python3 (any argument makes it print a Store hint and exit non-zero), and
# a real install passes. No usable interpreter: exit 0 silently — hooks must
# never disturb a session.
if python3 --version >/dev/null 2>&1; then
  exec python3 "${CLAUDE_PLUGIN_ROOT}/hooks/session_end.py"
fi
if python --version >/dev/null 2>&1; then
  exec python "${CLAUDE_PLUGIN_ROOT}/hooks/session_end.py"
fi
exit 0
