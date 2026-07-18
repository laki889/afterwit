# Afterwit

**Turn your Claude Code sessions into a permanent, searchable engineering
logbook — automatically, and 100% on your machine.**

[![tests](https://github.com/laki889/afterwit/actions/workflows/tests.yml/badge.svg)](https://github.com/laki889/afterwit/actions/workflows/tests.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![python: 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)

You solve dozens of problems with Claude Code, then forget the lessons: the
gotchas, the root causes, the decisions that worked. They're buried in chat
history nobody re-reads — and Claude Code purges transcripts after ~30 days.

Afterwit turns those sessions into a growing knowledge base in three stages:

- **Capture** — when a session ends, it's queued instantly (no LLM call, no
  delay).
- **Distill** — `afterwit sync` reads each queued transcript and extracts only
  the genuinely reusable lessons: named patterns, root causes, fixes worth
  repeating. Junk (typos, one-offs, noise) is filtered out.
- **Resurface** — every new session quietly opens with your most relevant
  recent lessons already in context, so you *and* Claude actually apply them.
  A CLI, a web dashboard, and a bundled MCP server let you browse, search, and
  spot trends across your full history.

*Afterwit (n., archaic): wisdom that comes only after the event.* The plugin
makes sure it arrives **before** the next one.

## Why Afterwit

- **Compounding memory.** Every session makes the next one smarter. Lessons are
  kept forever, even as Claude Code purges the transcripts they came from.
- **Reflect and improve.** A built-in dashboard to review what you've learned,
  spot recurring patterns in how you work, and watch your growth over time — a
  mirror on your progress, not just a store for it.
- **Zero friction.** Install it and keep working. Capture is automatic;
  distillation is one command (or a scheduled job); resurfacing needs nothing
  at all.
- **Private by design.** No accounts, no servers, no telemetry — see below.
- **No lock-in.** Your lessons are a plain SQLite file you own and can open
  with any tool.

## Privacy: everything stays on your machine

- **No remote backend, no telemetry, no analytics, no external API calls.** The
  one and only outbound call is the distillation itself, and it goes to the AI
  you already use: your own `claude` CLI (your existing account — no new party
  sees your data) or, for maximum privacy, a **local Ollama model** (nothing
  reaches Anthropic at all). The Ollama backend hard-refuses non-loopback URLs.
- Lessons live in a plain SQLite file **outside the plugin directory**, so
  plugin updates and uninstalls never touch them.
- Afterwit stores the distilled lessons, not raw transcripts, and the
  extraction prompt forbids copying secrets into lessons.
- The whole plugin is a few small, dependency-free Python files — audit it in
  one sitting. `grep -rn "urllib\|socket\|http" plugins/afterwit/src` finds
  exactly one **outbound** call site (the loopback-only Ollama backend) and one
  **inbound** one (the dashboard's `http.server`, hard-bound to 127.0.0.1 with
  Host-header validation against DNS rebinding). The dashboard page itself
  loads no external fonts, scripts, or styles.

## Requirements

- Claude Code
- Python 3.9+ (`python3` on PATH — preinstalled on macOS and most Linux
  distros; see [Windows](#windows) for notes on that platform)

## Install

```
/plugin marketplace add laki889/afterwit
/plugin install afterwit@afterwit
```

That's it — no config, no accounts, no setup. The hooks and database
initialize themselves.

To install from a local clone instead (for development, or before trusting a
remote): `/plugin marketplace add /path/to/afterwit`, then the same install
command. After pulling updates, run `/plugin marketplace update afterwit` and
`/plugin update afterwit@afterwit`.

## First run: backfill your existing history

Capture normally starts with the first session that ends *after* you install
Afterwit — so a fresh install begins with an empty database. But your existing
history is still on disk (until Claude Code's ~30-day cleanup purges it), and
that's often where your best lessons are.

**Run this once, right after installing, to get value immediately instead of
starting from zero:**

```
/afterwit:backfill        # in a session — queues your pre-existing sessions
/afterwit:sync            # then distill them into lessons
```

`backfill` scans Claude Code's transcript store newest-first and queues your
past sessions (10 by default) for distillation. It's idempotent — already-seen
sessions are skipped, so re-running is always safe — and it applies the same
quality bar as normal capture, so trivial sessions don't waste an LLM call.

Tune the scope with flags:

```
/afterwit:backfill --limit 25            # queue more history
/afterwit:backfill --days 14             # only the last two weeks
/afterwit:backfill --project my-app      # only one project
/afterwit:backfill --dry-run             # preview what would be queued
```

Do this soon after installing: Claude Code purges old transcripts on its own
retention schedule (~30 days), and a transcript that's already gone can't be
distilled.

> Both `/afterwit:backfill` and `afterwit backfill` (the bundled CLI) do the
> same thing. Inside a session the slash command is easiest; the CLI form is
> handy from a terminal or a script.

## Everyday use

1. **Work with Claude Code as usual.** Finished sessions are queued
   automatically.
2. **Distill whenever you like** (or [schedule it](#scheduling-sync)):
   ```
   afterwit sync            # inside a session (the plugin's bin/ is on PATH)
   /afterwit:sync           # or as a slash command
   ```
3. **New sessions open with your recent lessons.** A short "lessons from your
   past sessions" block is injected automatically into Claude's context at the
   start of each fresh session — silently, so it never clutters your chat: only
   Claude sees the lessons, and there's nothing for you to run.
4. **Browse and search from the CLI:**
   ```
   afterwit list            # newest lessons
   afterwit search sqlite   # full-text search
   afterwit stats           # trends, top tags, lessons over time
   afterwit queue           # sessions waiting for sync
   afterwit delete <id>     # lessons are never auto-deleted; this is manual
   ```
   For a visual way to review and reflect on everything you've learned, see
   [the dashboard](#reflect-on-your-progress-the-dashboard) below.

### Ask Claude directly

The plugin bundles a local MCP server (`lessons`) with read-only tools —
`query_lessons`, `recent_lessons`, and `lesson_stats` — so mid-session
questions like *"what have I learned about async retries?"* are answered from
your own database. It's fully local and never writes.

Two slash commands and a skill round this out:

- `/afterwit:review` — a reflective digest of your recent lessons, in-session.
- `/afterwit:search <query>` — query the database mid-conversation.
- the `/afterwit:lessons` skill — teaches Claude to check your lessons on its
  own before re-solving a problem you've already hit.

### Running the CLI outside a session

Inside a session the plugin's `bin/` is on your PATH, so `afterwit …` just
works. Outside one, call the installed CLI directly. The last path segment is a
per-version hash, so resolve it with a glob:

```sh
"$(ls -td ~/.claude/plugins/cache/afterwit/afterwit/*/ | head -1)bin/afterwit" stats
```

Or clone this repo anywhere and run `plugins/afterwit/bin/afterwit` from the
checkout — every copy of the CLI reads the same database.

## Reflect on your progress: the dashboard

Capturing lessons is only half the value — the other half is stepping back to
see what they add up to. Afterwit ships a local web dashboard that turns your
lessons database into a space for reflection: review what you've learned, spot
patterns in how you work, and watch your growth accumulate over time.

```
afterwit serve           # local dashboard at http://127.0.0.1:8377
```

- **Revisit what you've learned.** Full-text search and quick filter chips
  (your top tags and projects, right beside the search bar) surface everything
  you've learned on a topic in seconds. Tag, project, and month filters — click
  a month bar, a tag, or a project — let you trace how your understanding of an
  area evolved over time.
- **See the patterns in how you work.** A timeline grouped by month and trend
  charts — live from the database, refreshed every few seconds — reveal the
  shape of your development: which topics keep recurring, how steadily you're
  turning experience into lessons, and where your growth is concentrated.
- **Sit with a single insight.** Feed cards show a short summary; "Learn more"
  opens a per-lesson page laying out what went wrong, the root cause, and how
  you fixed it (deep-linkable at `#/lesson/<id>`) — so a hard-won insight
  actually sticks instead of scrolling past.

Want a snapshot to keep, read offline, or look back on later? `afterwit report`
writes that same page as a single portable, self-contained HTML file with the
data inlined — double-click it, no server needed (`#/lesson/<id>` deep links
work there too). And in-session, `/afterwit:serve` starts the dashboard in the
background (it stops when the session ends; use `afterwit serve` in a terminal
for a persistent one).

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
- Sessions are processed exactly once; a session that fails gets up to 3 total
  attempts across sync runs. If the backend itself is unavailable (CLI missing
  from PATH, not authenticated, Ollama down), the run aborts without consuming
  attempts — nothing is ever dropped because of an environment problem.

## Scheduling sync

Transcripts are purged after ~30 days (`cleanupPeriodDays` in Claude Code's
`settings.json` — raise it if you want more slack), so distill regularly.
Lessons themselves are kept forever.

The installed plugin lives under a per-version hash directory, so scheduled
jobs should resolve it with a glob (or run from a stable `git clone` of this
repo — any copy of the CLI reads the same database).

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

**Linux (cron)** — `crontab -e` (cron's PATH is minimal, so add the directory
containing the `claude` binary — find it with `which claude`):

```
0 13 * * * PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:$PATH" "$(ls -td "$HOME"/.claude/plugins/cache/afterwit/afterwit/*/ | head -1)bin/afterwit" sync
```

If `claude` isn't reachable from the job's PATH, sync aborts cleanly and the
queue is untouched — nothing is lost, but nothing is distilled either, so check
the job's output once after setting it up.

**Claude Code Desktop** users can instead create a daily scheduled task
("Routines" page) that runs `afterwit sync` — it executes locally.

## Configuration (optional)

Config lives at `~/.local/share/afterwit/config.json` (run `afterwit paths` to
confirm the location). Every key is optional — note that it's plain JSON, so no
comments are allowed. The full set, with defaults:

| Key | Default | Meaning |
|---|---|---|
| `backend` | `"claude"` | Inference for `sync`: `"claude"` (your own CLI) or `"ollama"` (max privacy) |
| `claude_model` | `null` | e.g. `"haiku"` to distill cheaply; `null` = your CLI's default model |
| `claude_timeout` | `600` | seconds per `claude -p` call |
| `ollama_url` | `"http://localhost:11434"` | must be loopback — anything else is refused |
| `ollama_model` | `"llama3.1"` | local model name (pull it first with `ollama pull`) |
| `ollama_timeout` | `600` | seconds per Ollama call |
| `inject_enabled` | `true` | SessionStart "recent lessons" block on/off |
| `inject_count` | `4` | lessons per new session (1–10) |
| `inject_min_confidence` | `0.0` | hide low-confidence lessons from injection |
| `min_confidence` | `0.3` | discard lessons the model itself doubts at sync time |
| `max_transcript_chars` | `200000` | rendering budget per session before distilling |

If the file is invalid JSON, `afterwit sync` warns on stderr and falls back to
the defaults. Two environment variables round out the configuration:
`AFTERWIT_DATA_DIR` relocates the whole data directory, and
`AFTERWIT_CLAUDE_BIN` points at a `claude` binary that isn't on PATH.

### Using the Ollama backend

For maximum privacy, set `"backend": "ollama"` to distill entirely on-device —
nothing reaches Anthropic. Start a local server (`ollama serve`), pull your
model (`ollama pull llama3.1`, or whatever you set for `ollama_model`), and run
`afterwit sync`. Afterwit talks only to a loopback address and refuses anything
else. Requests use Ollama's JSON mode so even smaller local models return
clean, parseable lessons.

## Troubleshooting

- **`sync` says "backend unavailable … not authenticated"** — run `claude auth
  login` in a terminal. Nothing was lost: environmental failures never consume
  retry attempts.
- **`sync` says "`claude` not found on PATH"** — from cron/launchd, add the
  binary's directory to the job's PATH (see [Scheduling](#scheduling-sync)), or
  set `AFTERWIT_CLAUDE_BIN=/path/to/claude`.
- **Ollama backend: "not reachable"** — start `ollama serve`. If it fails with
  "mkdir ~/.ollama: file exists", `~/.ollama` isn't a usable directory — most
  often a stray *file* by that name, or a **symlink to an unmounted volume**
  (`ls -la ~/.ollama`). Remove the file, mount the volume, or repoint
  `OLLAMA_MODELS` at a real directory.
- **Ollama backend: "model … is not available"** — the configured model isn't
  pulled yet. Run `ollama pull <model>` (default `llama3.1`), or set a
  different `ollama_model`. Like the other environmental failures, this aborts
  the run without consuming retry attempts, so nothing in the queue is lost.
- **`serve` says "cannot bind 127.0.0.1:8377"** — another instance is running;
  reuse it, or pass `--port 8378`.
- **No lessons block at session start** — the block appears only on fresh
  starts (`startup`/`clear`, not resume), only when the database has lessons,
  and only if `inject_enabled` is true.
- **Sessions pile up in `afterwit queue`** — that's by design; nothing is
  distilled until you run `sync` (schedule it, above).
- **Where is everything?** — run `afterwit paths`.

## Windows

Claude Code runs plugin commands through Git Bash. The CLI launcher and hooks
probe for a *working* interpreter (`python3`, then `python`) and skip the
Microsoft-Store alias stub, so any real Python 3.9+ install works. The CLI,
hooks, and MCP server force UTF-8 on their pipes (Windows consoles default to
cp1252), queue locking uses msvcrt byte-range locks, and an npm-installed
`claude.cmd` resolves for `sync`. Data lives under `%LOCALAPPDATA%\afterwit`.

One caveat: the bundled MCP server is spawned as `python3` by default (MCP
config can't probe). If `/mcp` shows the `lessons` server failing, set the
`AFTERWIT_PYTHON` environment variable to your interpreter (e.g. `python`) and
restart Claude Code.

## Uninstall

```
/plugin uninstall afterwit
```

Your lessons survive this: the database lives outside the plugin directory. To
delete the data too, remove the directory that `afterwit paths` prints (default
`~/.local/share/afterwit`).

## Your data is yours

The database is a plain SQLite file (`afterwit paths` shows where). Open it with
any SQLite tool — DB Browser, `sqlite3`, a VS Code extension. The CLI is
convenience, not lock-in.

The schema (authoritative copy in `plugins/afterwit/src/afterwit/store.py`;
dump yours with `sqlite3 "$(afterwit paths | awk '/database/{print $2}')"
.schema`):

| Table | Purpose |
|---|---|
| `lessons` | one row per lesson: `title`, `problem`, `root_cause`, `resolution`, `lesson`, `confidence` (0–1), `project`, `session_id` + `source_ts` (provenance), `created_at`, `dedup_key` (normalized title key; UNIQUE per project) |
| `tags` | lesson↔tag pairs (`ON DELETE CASCADE`) |
| `processed_sessions` | which session ids were already distilled, when, and how many lessons they yielded |
| `meta` | `schema_version` for in-place migrations |
| `lessons_fts` | FTS5 index over title/problem/lesson/resolution, kept in sync by triggers (absent if your SQLite lacks FTS5 — search falls back to LIKE) |

Timestamps are UTC ISO-8601 strings. Lessons are never auto-deleted; `afterwit
delete <id>` is the only destructive operation, and the FTS triggers keep the
index consistent when you use it. Note that transcripts (Claude Code's own
files) may contain sensitive values; Afterwit stores only the distilled lessons
and tells the model to keep secrets out of them — but review `afterwit list -v`
output before sharing it anywhere.

## Development

Everything is stdlib Python — no install step:

```
python3 -m unittest discover -s tests        # 99 tests, ~6s
AFTERWIT_DATA_DIR=$(mktemp -d) plugins/afterwit/bin/afterwit paths   # sandboxed run
```

`AFTERWIT_DATA_DIR` points every entry point (CLI, hooks, MCP server) at an
alternate data directory, so you can exercise anything against throwaway data
without touching your real lessons. `tests/fixtures/` contains a synthetic
transcript that mirrors the real JSONL format; verified platform schemas live
in [docs/platform-notes.md](docs/platform-notes.md).

See [CONTRIBUTING.md](CONTRIBUTING.md) for the ground rules — the short
version: nothing may add a network call, a dependency, or a write path to the
readers.

## License

MIT — see [LICENSE](LICENSE).
