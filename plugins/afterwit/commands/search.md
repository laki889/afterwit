---
description: Search your lessons-learned database (full-text, local)
argument-hint: "<query>"
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/afterwit" *)
---

Search the local afterwit lessons database for: $ARGUMENTS

Run this with the Bash tool, passing the query as properly quoted arguments
(never interpolate it into a shell string unquoted):

```
"${CLAUDE_PLUGIN_ROOT}/bin/afterwit" search --limit 10 -v <query words>
```

Then summarize the results for the user, most relevant first. If a lesson
directly applies to what they're currently working on, say so explicitly.
If there are no results, say so and suggest running /afterwit:sync if the
queue has pending sessions (`"${CLAUDE_PLUGIN_ROOT}/bin/afterwit" queue`).
