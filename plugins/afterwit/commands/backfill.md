---
description: Queue Claude Code sessions from before afterwit was installed (first-install import)
argument-hint: "[--limit N] [--days N] [--project X] [--dry-run]"
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/afterwit" *)
---

Queue pre-existing sessions from Claude Code's local transcript store (the
newest 10 eligible by default):

```
"${CLAUDE_PLUGIN_ROOT}/bin/afterwit" backfill $ARGUMENTS
```

Run it with the Bash tool, then report the summary to the user: how many
sessions were queued and why the rest were skipped (already known, possibly
live, trivial, other projects). It is idempotent — re-running is always safe.

If sessions were queued, remind the user to run /afterwit:sync soon:
Claude Code purges old transcripts on its own retention schedule, and a
queue entry alone does not preserve the transcript. If nothing was queued,
say so plainly and mention `--days`/`--limit` if the store simply had
nothing new.
