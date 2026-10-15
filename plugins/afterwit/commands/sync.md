---
description: Distill queued Claude Code sessions into lessons (sends each transcript to your own claude CLI, or to a local Ollama model)
argument-hint: "[--dry-run] [--project NAME] [--limit N] [--backend claude|ollama]"
disable-model-invocation: true
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/afterwit" *)
---

Run the afterwit distillation pipeline over the queued sessions:

```
"${CLAUDE_PLUGIN_ROOT}/bin/afterwit" sync $ARGUMENTS
```

Run it with the Bash tool (it may take a minute or two per session — it sends
each queued transcript to the backend once per session; use run_in_background
if the queue is long).

The command's first output line names the active backend. Relay it to the
user before the results:

- `claude` backend (the default): queued transcripts from any project are
  sent through their own `claude` CLI to the Claude account it is currently
  signed in to, and those calls count toward that account's usage.
- `ollama` backend: distillation runs fully on this machine.

Then report the summary line: how many sessions were processed, how many new
lessons were stored, and any failures. If it fails with an authentication
error, tell the user to run `claude auth login` in a terminal (or switch to
the on-device backend with `--backend ollama`).
