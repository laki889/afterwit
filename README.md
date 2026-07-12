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
  exactly one network call site — the loopback-only Ollama backend.

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

Outside a session, call the CLI directly (or symlink it onto your PATH):

```
~/.claude/plugins/cache/afterwit/plugins/afterwit/bin/afterwit stats
```

## How it works

```
[ session ends ]                                [ new session starts ]
      │ SessionEnd hook (instant, no LLM)             ▲
      ▼                                               │ SessionStart hook
queue.jsonl ──► afterwit sync ──► SQLite DB ──────────┘ injects recent lessons
               (parse JSONL,      (~/.local/share/afterwit/afterwit.db,
                distill via YOUR   lessons kept forever, WAL, readers
                claude/Ollama)     open read-only)
```

- The transcript parser groups streamed assistant chunks by message id
  (transcripts are *not* one-message-per-line) and tolerates corrupt lines,
  meta records, and subagent sidechains.
- Dedup happens twice: the extraction prompt sees your existing lesson titles,
  and a normalized key catches near-duplicates locally.
- Sessions are processed exactly once; failures are retried up to 3 times.

## Scheduling sync

Transcripts are purged after ~30 days (`cleanupPeriodDays` in Claude Code's
settings.json — raise it if you want more slack), so distill regularly.
Lessons themselves are kept forever.

**macOS (launchd)** — `~/Library/LaunchAgents/dev.afterwit.sync.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>dev.afterwit.sync</string>
  <key>ProgramArguments</key><array>
    <string>/bin/sh</string><string>-c</string>
    <string>"$HOME"/.claude/plugins/cache/afterwit/plugins/afterwit/bin/afterwit sync</string>
  </array>
  <key>StartCalendarInterval</key><dict>
    <key>Hour</key><integer>13</integer><key>Minute</key><integer>0</integer>
  </dict>
</dict></plist>
```

Then `launchctl load ~/Library/LaunchAgents/dev.afterwit.sync.plist`.

**Linux (cron)** — `crontab -e`:

```
0 13 * * * "$HOME"/.claude/plugins/cache/afterwit/plugins/afterwit/bin/afterwit sync
```

**Claude Code Desktop** users can instead create a daily scheduled task
("Routines" page) that runs `afterwit sync` — it executes locally.

## Configuration (optional)

`~/.local/share/afterwit/config.json` (see `afterwit paths`):

```json
{
  "backend": "claude",          // or "ollama" (max privacy)
  "claude_model": null,         // e.g. "haiku" to distill cheaply
  "ollama_model": "llama3.1",
  "inject_enabled": true,       // SessionStart lessons block
  "inject_count": 4,            // lessons per new session
  "min_confidence": 0.3         // discard lessons the model itself doubts
}
```

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
