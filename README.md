# Afterwit

**Systematic self-reflection from your own Claude Code sessions — automatic
lessons-learned, 100% local, nothing leaves your machine. Read every line.**

You solve dozens of problems with Claude Code, then forget the lessons: the
gotchas, the root causes, the decisions that worked. They're buried in chat
history nobody re-reads — and Claude Code purges transcripts after ~30 days.

Afterwit turns those sessions into a permanent, growing engineering logbook:

- **Capture** — when a session ends, it's queued (instantly, no LLM call).
- **Distill** — `afterwit sync` reads each queued transcript and extracts only
  the genuinely reusable lessons: named patterns, root causes, fixes worth
  repeating. Junk (typos, one-offs, noise) is filtered out.
- **Resurface** — every new session quietly starts with your most relevant
  recent lessons in context, so you (and Claude) actually apply them. A CLI
  lets you browse, search, and see trends across your full history.

*Afterwit (n., archaic): wisdom that comes only after the event.* The plugin
makes sure it arrives **before** the next one.

## Privacy: everything stays on your machine

- **No remote backend, no telemetry, no analytics, no external API calls.**
  The one and only outbound call is the distillation itself, and it goes to
  the AI you already use: your own `claude` CLI (your existing account — no
  new party sees your data) or, for maximum privacy, a **local Ollama model**
  (nothing reaches Anthropic at all). The Ollama backend hard-refuses
  non-loopback URLs.
- Lessons live in a plain SQLite file **outside the plugin directory**, so
  plugin updates and uninstalls never touch them.
- We store the distilled lessons, not raw transcripts, and the extraction
  prompt forbids copying secrets into lessons.
- The whole plugin is a few small, dependency-free Python files. Audit it in
  one sitting: `grep -rn "urllib\|socket\|http" plugins/afterwit/src` finds
  exactly one **outbound** call site (the loopback-only Ollama backend) and
  one **inbound** one (the dashboard's `http.server`, hard-bound to
  127.0.0.1 with Host-header validation against DNS rebinding). The
  dashboard page itself loads no external fonts, scripts, or styles.

## Install

Requires Claude Code and Python 3.9+ (`python3` on PATH — preinstalled on
macOS and most Linux distros).

```
/plugin marketplace add laki889/afterwit
/plugin install afterwit@afterwit
```

That's it — no config, no accounts, no setup. The hooks and database
initialize themselves.

Already have session history on this machine? Capture normally starts with
the first session that ends *after* install, but `afterwit backfill` (or
`/afterwit:backfill` in-session) queues your existing sessions too
(newest-first, 10 by default; `--limit N`, `--days N`, `--project X`,
`--dry-run`). Run it soon after installing and
follow with `afterwit sync` — Claude Code purges old transcripts on its own
retention schedule (~30 days).

To install from a local clone instead (development, or before trusting a
remote): `/plugin marketplace add /path/to/afterwit` then the same install
command. After pulling updates run `/plugin marketplace update afterwit`
and `/plugin update afterwit@afterwit`.

## Use

1. Work with Claude Code as usual. Finished sessions are queued automatically.
2. Distill whenever you like (or schedule it, below):
   ```
   afterwit sync            # inside a Claude Code session (bin/ is on PATH)
   /afterwit:sync           # or as a slash command
   ```
3. New sessions automatically open with a short "lessons from your past
   sessions" block. Browse the history any time:
   ```
   afterwit backfill        # first install? queue pre-existing sessions
   afterwit list            # newest lessons
   afterwit search sqlite   # full-text search
   afterwit stats           # trends, top tags, lessons over time
   afterwit queue           # sessions waiting for sync
   afterwit delete <id>     # lessons are never auto-deleted; this is manual
   ```
   `/afterwit:review` gives you a reflective digest in-session,
   `/afterwit:search <query>` queries the database mid-conversation, and
   the `/afterwit:lessons` skill teaches Claude to check your lessons on
   its own before re-solving an old problem.
4. Browse the full history visually:
   ```
   afterwit serve           # local dashboard at http://127.0.0.1:8377
   afterwit report          # write lessons.html — a self-contained snapshot
   ```
   The dashboard has full-text search, quick filter chips beside the
   search bar (top tags + projects), tag/project/month filters (click a
   month bar, a tag, or a project), a timeline grouped by month, and trend
   charts — live from the database, refreshed every few seconds. Feed
   cards show a short summary; "Learn more" opens a per-lesson page with
   what went wrong, the root cause, and how it was fixed (deep-linkable
   `#/lesson/<id>`, works in the snapshot too). `report`
   produces the same page as a single portable HTML file with the data
   inlined: double-click it, no server needed. In-session, `/afterwit:serve`
   starts the same dashboard in the background (it stops when the session
   ends; use the terminal for a persistent one).
5. Ask Claude directly. The plugin bundles a local MCP server (`lessons`)
   with read-only tools — `query_lessons`, `recent_lessons`,
   `lesson_stats` — so mid-session questions like *"what have I learned
   about async retries?"* are answered from your own database. Fully local,
   never writes.

Outside a session, call the CLI from the installed plugin (the last path
segment is a version hash, so resolve it with a glob):

```sh
"$(ls -td ~/.claude/plugins/cache/afterwit/afterwit/*/ | head -1)bin/afterwit" stats
```

or clone this repo anywhere and run `plugins/afterwit/bin/afterwit` from the
checkout — every copy of the CLI reads the same database.

## How it works

```
[ session ends ]                                [ new session starts ]
      │ SessionEnd hook (instant, no LLM)             ▲
      ▼                                               │ SessionStart hook
queue.jsonl ──► afterwit sync ──► SQLite DB ──────────┘ injects recent lessons
               (parse JSONL,      (~/.local/share/afterwit/afterwit.db,
                distill via YOUR   lessons kept forever, WAL, readers
                claude/Ollama)     open read-only)
                                      │
                                      ├──► afterwit serve   (127.0.0.1 dashboard)
                                      └──► afterwit report  (portable lessons.html)
```

- The transcript parser groups streamed assistant chunks by message id
  (transcripts are *not* one-message-per-line) and tolerates corrupt lines,
  meta records, and subagent sidechains.
- Dedup happens twice: the extraction prompt sees your existing lesson titles,
  and a normalized key catches near-duplicates locally.
- Sessions are processed exactly once; a session that fails gets up to 3
  total attempts across sync runs. If the backend itself is unavailable
  (CLI missing from PATH, not authenticated, Ollama down), the run aborts
  without consuming attempts — nothing is ever dropped because of an
  environment problem.

## Scheduling sync

Transcripts are purged after ~30 days (`cleanupPeriodDays` in Claude Code's
settings.json — raise it if you want more slack), so distill regularly.
Lessons themselves are kept forever.

The installed plugin lives under a per-version hash directory, so scheduled
jobs should resolve it with a glob (or run from a stable `git clone` of this
repo — any copy of the CLI reads the same database):

**macOS (launchd)** — `~/Library/LaunchAgents/dev.afterwit.sync.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>dev.afterwit.sync</string>
  <key>ProgramArguments</key><array>
    <string>/bin/sh</string><string>-c</string>
    <string>export PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"; "$(ls -td "$HOME"/.claude/plugins/cache/afterwit/afterwit/*/ | head -1)bin/afterwit" sync</string>
  </array>
  <key>StartCalendarInterval</key><dict>
    <key>Hour</key><integer>13</integer><key>Minute</key><integer>0</integer>
  </dict>
</dict></plist>
```

Then `launchctl load ~/Library/LaunchAgents/dev.afterwit.sync.plist`.

**Linux (cron)** — `crontab -e` (cron's PATH is minimal, so add the
directory containing the `claude` binary — find it with `which claude`):

```
0 13 * * * PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:$PATH" "$(ls -td "$HOME"/.claude/plugins/cache/afterwit/afterwit/*/ | head -1)bin/afterwit" sync
```

If `claude` isn't reachable from the job's PATH, sync aborts cleanly and the
queue is untouched — nothing is lost, but nothing is distilled either, so
check the job's output once after setting it up.

**Claude Code Desktop** users can instead create a daily scheduled task
("Routines" page) that runs `afterwit sync` — it executes locally.

## Configuration (optional)

`~/.local/share/afterwit/config.json` (see `afterwit paths`). Every key is
optional (note: JSON — no comments allowed). The full set, with defaults:

| Key | Default | Meaning |
|---|---|---|
| `backend` | `"claude"` | Inference for `sync`: `"claude"` (your own CLI) or `"ollama"` (max privacy) |
| `claude_model` | `null` | e.g. `"haiku"` to distill cheaply; `null` = your CLI's default model |
| `claude_timeout` | `600` | seconds per `claude -p` call |
| `ollama_url` | `"http://localhost:11434"` | must be loopback — anything else is refused |
| `ollama_model` | `"llama3.1"` | local model name |
| `ollama_timeout` | `600` | seconds per Ollama call |
| `inject_enabled` | `true` | SessionStart "recent lessons" block on/off |
| `inject_count` | `4` | lessons per new session (1–10) |
| `inject_min_confidence` | `0.0` | hide low-confidence lessons from injection |
| `min_confidence` | `0.3` | discard lessons the model itself doubts at sync time |
| `max_transcript_chars` | `200000` | rendering budget per session before distilling |

If the file is invalid JSON, `afterwit sync` warns on stderr and uses the
defaults. `AFTERWIT_DATA_DIR` (env) relocates the whole data dir;
`AFTERWIT_CLAUDE_BIN` (env) points at a non-PATH `claude` binary.

## Troubleshooting

- **`sync` says "backend unavailable … not authenticated"** — run
  `claude auth login` in a terminal. Nothing was lost: environmental
  failures never consume retry attempts.
- **`sync` says "`claude` not found on PATH"** — from cron/launchd, add the
  binary's directory to the job's PATH (see Scheduling), or set
  `AFTERWIT_CLAUDE_BIN=/path/to/claude`.
- **Ollama backend: "not reachable"** — start `ollama serve` and pull the
  configured model. If it fails with "mkdir ~/.ollama: file exists", a stray
  *file* named `~/.ollama` is blocking it — remove that file.
- **`serve` says "cannot bind 127.0.0.1:8377"** — another instance is
  running; reuse it or pass `--port 8378`.
- **No lessons block at session start** — the block appears only on fresh
  starts (`startup`/`clear`, not resume), only when the DB has lessons, and
  only if `inject_enabled` is true.
- **Sessions pile up in `afterwit queue`** — that's by design; nothing is
  distilled until you run `sync` (schedule it, below).
- **Where is everything?** — `afterwit paths`.

## Uninstall

```
/plugin uninstall afterwit
```

Your lessons are yours and survive this: the database lives outside the
plugin. To delete the data too, remove the directory `afterwit paths`
prints (default `~/.local/share/afterwit`).

## Your data is yours

The database is a plain SQLite file (`afterwit paths` shows where). Open it
with any SQLite tool — DB Browser, `sqlite3`, a VS Code extension. The CLI is
convenience, not lock-in.

The schema (authoritative copy in `src/afterwit/store.py`; dump yours with
`sqlite3 "$(afterwit paths | awk '/database/{print $2}')" .schema`):

| Table | Purpose |
|---|---|
| `lessons` | one row per lesson: `title`, `problem`, `root_cause`, `resolution`, `lesson`, `confidence` (0–1), `project`, `session_id` + `source_ts` (provenance), `created_at`, `dedup_key` (normalized title key; UNIQUE per project) |
| `tags` | lesson↔tag pairs (`ON DELETE CASCADE`) |
| `processed_sessions` | which session ids were already distilled, when, and how many lessons they yielded |
| `meta` | `schema_version` for in-place migrations |
| `lessons_fts` | FTS5 index over title/problem/lesson/resolution, kept in sync by triggers (absent if your SQLite lacks FTS5 — search falls back to LIKE) |

Timestamps are UTC ISO-8601 strings. Lessons are never auto-deleted;
`afterwit delete <id>` is the only destructive operation, and the FTS
triggers keep the index consistent when you use it. Note: transcripts (Claude Code's own files) may
contain sensitive values; afterwit stores only the distilled lessons and
tells the model to keep secrets out of them — but review `afterwit list -v`
output before sharing it anywhere.

## Windows

Claude Code runs plugin commands through Git Bash. The CLI launcher and
hooks probe for a *working* interpreter (`python3`, then `python`) and
skip the Microsoft-Store alias stub, so any real Python 3.9+ install
works. The CLI, hooks, and MCP server force UTF-8 on their pipes (Windows
consoles default to cp1252), queue locking uses msvcrt byte-range locks,
and an npm-installed `claude.cmd` resolves for `sync`. Data lives under
`%LOCALAPPDATA%\afterwit`.

One caveat: the bundled MCP server is spawned as `python3` by default
(MCP config can't probe). If `/mcp` shows the `lessons` server failing,
set the `AFTERWIT_PYTHON` environment variable to your interpreter
(e.g. `python`) and restart Claude Code.

## Development

Everything is stdlib Python — no install step:

```
python3 -m unittest discover -s tests        # 73 tests, ~6s
AFTERWIT_DATA_DIR=$(mktemp -d) plugins/afterwit/bin/afterwit paths   # sandboxed run
```

`AFTERWIT_DATA_DIR` points every entry point (CLI, hooks, MCP server) at an
alternate data directory, so you can exercise anything against throwaway
data without touching your real lessons. `tests/fixtures/` contains a
synthetic transcript that mirrors the real JSONL format; verified platform
schemas live in [docs/platform-notes.md](docs/platform-notes.md). See
[CONTRIBUTING.md](CONTRIBUTING.md) for the ground rules — the short
version: nothing may add a network call, a dependency, or a write path to
the readers.

## License

MIT — see [LICENSE](LICENSE).
