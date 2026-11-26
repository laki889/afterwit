#!/bin/sh
# Launcher for the afterwit CLI — a plain shell script, like the hook
# launchers, that runs afterwit_cli.py (the file beside it) with a WORKING
# interpreter. The plugin ships no bin/ directory and no compiled programs:
# everything it runs is readable source in this folder tree.
#
# The slash commands call it as "${CLAUDE_PLUGIN_ROOT}/scripts/afterwit.sh";
# from a terminal, cron or launchd, call it by its full path (README:
# "Running the CLI outside a session"). It must be called by path, not through
# a symlink: it finds afterwit_cli.py relative to its own location.
#
# Probe python3 first, then python. `--version` rejects the Microsoft-Store
# alias stub that sits on PATH pretending to be python3 (any argument makes it
# print a Store hint and exit non-zero), and a real install passes.
case "$0" in
  */*) here="${0%/*}" ;;
  *) here="." ;;
esac
if python3 --version >/dev/null 2>&1; then
  exec python3 "$here/afterwit_cli.py" "$@"
fi
if python --version >/dev/null 2>&1; then
  exec python "$here/afterwit_cli.py" "$@"
fi
echo "afterwit: no usable python3/python found on PATH" >&2
exit 1
