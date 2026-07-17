# Changelog

## Unreleased

- `/afterwit:serve` slash command: opens the local dashboard from inside a
  session (background server, browser auto-open; stops when the session
  ends — use `afterwit serve` in a terminal for a persistent one).
- All slash commands pre-approve their own bundled-CLI calls via
  `allowed-tools`, removing the per-invocation permission prompt.

## 0.3.0 — 2026-07-16

- Bundled MCP server (`lessons`): read-only `query_lessons`,
  `recent_lessons`, and `lesson_stats` tools over the local database, so
  Claude can consult past lessons mid-session. Stdlib-only JSON-RPC/stdio;
  never writes, never touches the network.
- Docs: full config reference, troubleshooting, uninstall, database
  schema, migration recipe, CONTRIBUTING.md with the privacy contract.
- Verified on Python 3.9 (macOS system Python) through 3.13.

## 0.2.0 — 2026-07-15

- `afterwit serve`: local web dashboard (127.0.0.1 only, Host-header
  validated, read-only, zero external assets) — search, tag/project/month
  filters, month-grouped timeline, trend charts, light/dark themes.
- `afterwit report`: the same dashboard as one portable, self-contained
  HTML snapshot with the data inlined (`--project` scopes both the feed
  and the recomputed stats).
- Hardening from adversarial review: DNS-rebinding defense, degraded-DB
  handling on `/api/data`, script-breakout escaping for inlined lesson
  content, keyboard-focus preservation across filter re-renders.

## 0.1.0 — 2026-07-13

Initial MVP.

- SessionEnd capture hook: instant, idempotent enqueue of finished sessions.
- `afterwit sync`: JSONL transcript parsing (message-id grouping), strict
  lesson extraction via the user's own `claude` CLI or a local Ollama model,
  two-layer dedup, retry policy.
- SessionStart hook: budgeted "recent lessons" context injection.
- SQLite store outside the plugin dir (XDG), WAL, FTS5 search with LIKE
  fallback, schema self-init and versioning.
- CLI: `sync`, `list`, `search`, `stats`, `queue`, `delete`, `paths`.
- Slash commands `/afterwit:sync`, `/afterwit:review`, `/afterwit:search`;
  `lessons` skill for in-session querying.
