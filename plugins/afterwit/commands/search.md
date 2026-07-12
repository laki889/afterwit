---
description: Search your lessons-learned database (full-text, local)
argument-hint: "<query>"
---

Search results from the local afterwit lessons database:

!`"${CLAUDE_PLUGIN_ROOT}/bin/afterwit" search --limit 10 -v $ARGUMENTS 2>&1`

Summarize the results above for the user, most relevant first. If a lesson
directly applies to what they're currently working on, say so explicitly.
If there are no results, say so and suggest running /afterwit:sync if the
queue has pending sessions.
