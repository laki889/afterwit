---
description: Open the local afterwit lessons dashboard in your browser (127.0.0.1 only)
argument-hint: "[--port N]"
disable-model-invocation: true
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/afterwit" *)
---

Start the local afterwit dashboard. Run this with the Bash tool with
run_in_background: true — it is a long-running server, so never run it in
the foreground:

```
"${CLAUDE_PLUGIN_ROOT}/bin/afterwit" serve --open $ARGUMENTS
```

Then tell the user the dashboard URL (http://127.0.0.1:8377, or their
--port if they passed one) and that the server stops when this Claude Code
session ends — for a persistent dashboard, run `afterwit serve` in a
regular terminal.

If it fails with "cannot bind", the dashboard is already running — that is
not an error; just give the user the URL.
