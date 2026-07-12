---
name: lessons
description: Query the developer's local lessons-learned database (built by the afterwit plugin from their past Claude Code sessions). Use when the user asks what they've learned before, whether they've hit a problem previously, or when starting work that smells like a past issue (same error, same subsystem, same tool). Read-only.
user-invocable: true
---

# Afterwit lessons database

This machine keeps a local SQLite database of distilled "lessons learned"
from the developer's past Claude Code sessions. It is 100% local.

## How to query it

Use the bundled CLI (read-only commands; `afterwit` is also on PATH inside
sessions via the plugin's bin/ directory):

```bash
"${CLAUDE_PLUGIN_ROOT}/bin/afterwit" search <keywords>   # full-text search
"${CLAUDE_PLUGIN_ROOT}/bin/afterwit" list --limit 10     # newest lessons
"${CLAUDE_PLUGIN_ROOT}/bin/afterwit" list --project <p>  # per project
"${CLAUDE_PLUGIN_ROOT}/bin/afterwit" list --tag <tag>    # per topic
"${CLAUDE_PLUGIN_ROOT}/bin/afterwit" stats               # trends and counts
```

Add `-v` to `search`/`list` for problem/root-cause/resolution detail.

## When to use it

- The user asks "have I hit this before?", "what have I learned about X?",
  or similar retrospection questions.
- You're debugging an error that plausibly recurred (check `search` with the
  error's key terms before re-deriving a fix from scratch).
- Before proposing an approach in an area where the database has lessons
  (a quick `search` costs nothing and may contain the exact gotcha).

## Rules

- Read-only: never modify the database; deletion is the user's explicit
  action via `afterwit delete <id>`.
- If a lesson conflicts with what you observe in the current codebase,
  trust the code and say the lesson may be stale.
- If the CLI reports there is no database yet, tell the user lessons will
  appear after their first `afterwit sync` (or /afterwit:sync).
