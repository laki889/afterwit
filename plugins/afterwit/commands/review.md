---
description: Review your recent lessons learned and reflect on patterns
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/scripts/afterwit.sh" *)
---

Current lessons digest (read locally from the afterwit database):

Recent lessons:
!`"${CLAUDE_PLUGIN_ROOT}/scripts/afterwit.sh" list --limit 15 2>&1`

Stats:
!`"${CLAUDE_PLUGIN_ROOT}/scripts/afterwit.sh" stats 2>&1`

Pending queue:
!`"${CLAUDE_PLUGIN_ROOT}/scripts/afterwit.sh" queue 2>&1`

Give the user a short reflective review of the digest above:
1. The 2-3 most significant recurring themes (use the tags and titles).
2. Anything they keep hitting repeatedly that deserves a durable fix
   (tooling, checklist, or CLAUDE.md addition).
3. If the pending queue is non-empty, remind them to run /afterwit:sync.
Keep it under ~200 words, concrete, and grounded ONLY in the digest above.
