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
/plugin marketplace add lazartrajkovic/afterwit
/plugin install afterwit@afterwit
```

That's it — no config, no accounts, no setup. The hooks and database
initialize themselves.

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
   afterwit list            # newest lessons
   afterwit search sqlite   # full-text search
   afterwit stats           # trends, top tags, lessons over time
   afterwit queue           # sessions waiting for sync
   afterwit delete <id>     # lessons are never auto-deleted; this is manual
   ```
   `/afterwit:review` gives you a reflective digest in-session, and
   `/afterwit:search <query>` queries the database mid-conversation.
4. Browse the full history visually:
   ```
   afterwit serve           # local dashboard at http://127.0.0.1:8377
   afterwit report          # write lessons.html — a self-contained snapshot
   ```
   The dashboard has full-text search, tag/project/month filters (click a
   month bar, a tag, or a project), a timeline grouped by month, and trend
   charts — live from the database, refreshed every few seconds. `report`
   produces the same page as a single portable HTML file with the data
   inlined: double-click it, no server needed.

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

`~/.local/share/afterwit/config.json` (see `afterwit paths`). All keys are
optional; this example shows the defaults (note: JSON — no comments allowed):

```json
{
  "backend": "claude",
  "claude_model": null,
  "ollama_model": "llama3.1",
  "inject_enabled": true,
  "inject_count": 4,
  "min_confidence": 0.3
}
```

- `backend` — `"claude"` (your own CLI) or `"ollama"` (max privacy).
- `claude_model` — e.g. `"haiku"` to distill cheaply; `null` = CLI default.
- `inject_enabled` / `inject_count` — the SessionStart lessons block.
- `min_confidence` — discard lessons the model itself doubts (0–1).

If the file is invalid JSON, `afterwit sync` warns on stderr and uses the
defaults.

## Your data is yours

The database is a plain SQLite file (`afterwit paths` shows where). Open it
with any SQLite tool — DB Browser, `sqlite3`, a VS Code extension. The CLI is
convenience, not lock-in. Note: transcripts (Claude Code's own files) may
contain sensitive values; afterwit stores only the distilled lessons and
tells the model to keep secrets out of them — but review `afterwit list -v`
output before sharing it anywhere.

## Windows

Hooks and CLI need `python3` (or `python`) on PATH inside Git Bash. Data
lives under `%LOCALAPPDATA%\afterwit`.

## License

MIT — see [LICENSE](LICENSE).
