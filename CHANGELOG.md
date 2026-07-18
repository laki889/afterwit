# Changelog

## Unreleased

## 0.4.0 — 2026-07-18

- Ollama backend hardening (max-privacy path now reliable end-to-end):
  requests use grammar-constrained JSON mode (`format: "json"`) and
  `temperature: 0`, so small local models stop wrapping the lesson array in
  prose/markdown; a not-yet-pulled model (HTTP 404) is now reported as an
  actionable `ollama pull <model>` hint and aborts the run without charging
  retries, instead of being misdiagnosed as "server not reachable". Covered by
  unit tests for every failure mode plus a real-socket end-to-end sync test.
- Windows support pass (every entry point had a real defect — found by a
  three-way platform/security/release review): UTF-8 forced at every pipe
  boundary (claude subprocess, CLI stdout, hook stdin, MCP stdio);
  `bin/afterwit` is now an sh/python polyglot that probes for a working
  interpreter (surviving a missing `python3` and the Microsoft-Store alias
  stub), and the hooks probe the same way; npm's `claude.cmd` resolves via
  PATHEXT; queue/sync locking gets an msvcrt fallback (closing a silent
  lost-queue-entry race); `.mcp.json` spawns `${AFTERWIT_PYTHON:-python3}`
  so Windows users have a documented override.
- CI: GitHub Actions matrix — Linux/macOS/Windows × Python 3.9/3.13.
- `afterwit backfill` (and the `/afterwit:backfill` slash command): queue
  sessions that predate the install from Claude Code's own transcript store
  (newest-first, 10 by default; `--limit`, `--days`, `--project`,
  `--dry-run`). Recovers project/cwd from the
  transcript itself, skips already-queued/processed sessions (idempotent),
  live sessions, extraction runs, subagent sidecars, and sessions below
  sync's triviality bar.
- Dashboard: quick filter chips beside the search bar (5 most popular
  tags + all projects), shorter lesson summaries in the feed, and a
  per-lesson detail page — lesson, what went wrong, root cause, and how
  it was fixed — on a deep-linkable client-side route (`#/lesson/<id>`)
  that works in both `serve` and the `report` snapshot.
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
