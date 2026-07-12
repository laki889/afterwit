# Changelog

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
