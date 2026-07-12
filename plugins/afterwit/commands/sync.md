---
description: Distill queued Claude Code sessions into lessons learned (runs locally)
argument-hint: "[--dry-run] [--project NAME] [--limit N] [--backend claude|ollama]"
---

Run the afterwit synthesis pipeline over the queued sessions:

```
"${CLAUDE_PLUGIN_ROOT}/bin/afterwit" sync $ARGUMENTS
```

Run it with the Bash tool (it may take a minute or two per session — it calls
the local `claude` CLI or Ollama once per queued session; use run_in_background
if the queue is long). Then report the summary line to the user: how many
sessions were processed, how many new lessons were stored, and any failures.
If it fails with an authentication error, tell the user to run `claude login`
(or switch to the Ollama backend with `--backend ollama`).
