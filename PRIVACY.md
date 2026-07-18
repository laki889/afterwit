# Privacy Policy

**Effective date: 2026-07-18**

Afterwit is a local-first Claude Code plugin. It is built so that your
development history — and the lessons distilled from it — never leave your
machine except through one path that you configure and control. This document
explains, precisely, what Afterwit does and does not do with your data.

In short: **Afterwit has no servers, collects no telemetry, and makes no
network calls of its own.** The only outbound connection is the lesson-
distillation step, and it goes to an AI backend that *you* choose — your own
`claude` CLI (your existing account) or a local Ollama model on your own
machine.

## Summary

| Question | Answer |
|---|---|
| Does Afterwit run a remote backend or server? | No. |
| Does it collect telemetry, analytics, or usage data? | No. |
| Does the plugin itself phone home or call any external API? | No. |
| Does any data leave my machine? | Only the transcript sent to the distillation backend *you* configure (your own `claude` CLI or a local Ollama model). Nothing else. |
| Where is my data stored? | In a plain SQLite file on your own machine, outside the plugin directory. |
| Can I delete everything? | Yes — one directory removal wipes all Afterwit data. |

## What data Afterwit handles

Afterwit works with two kinds of data, both already present on your machine:

- **Session transcripts** — the `.jsonl` files Claude Code writes for your
  sessions. Afterwit reads them locally to distill lessons. It does **not**
  copy, upload, or retain raw transcripts; they remain Claude Code's own files
  under its own retention policy.
- **Distilled lessons** — the short, reusable takeaways Afterwit extracts (a
  title, the problem, the root cause, the resolution, the lesson, tags, and a
  confidence score). These are what Afterwit stores.

Afterwit stores only the distilled lessons, never the raw transcripts.

## What leaves your machine

The plugin makes **no network calls of its own** — no telemetry, no analytics,
no update checks, no external API calls.

The single exception is the distillation step, which you invoke with
`afterwit sync`. To turn a transcript into lessons, that transcript text is
sent to the inference backend you have configured:

- **`claude` backend (default).** The transcript is passed to your own local
  `claude` CLI, running under your existing Claude Code account. No new party
  receives your data — it goes to the same service you are already using with
  Claude Code.
- **`ollama` backend (maximum privacy).** The transcript is sent to a local
  Ollama server on your own machine, so nothing reaches Anthropic or any other
  external service. Afterwit validates that the Ollama URL is a loopback
  address (`localhost` / `127.0.0.1` / `::1`) and **refuses to send data to any
  non-loopback host.** It also bypasses any configured HTTP proxy so the
  transcript cannot be routed off-machine.

You control which backend is used via `config.json` (`"backend": "claude"` or
`"ollama"`). No transcript is ever sent anywhere until you run `afterwit sync`.

## Where your data is stored

Lessons live in a plain SQLite database on your machine, in a data directory
**outside the plugin directory** so that plugin updates and uninstalls never
touch it:

- **macOS / Linux:** `~/.local/share/afterwit` (XDG-respecting)
- **Windows:** `%LOCALAPPDATA%\afterwit`

Run `afterwit paths` at any time to see the exact locations of the data
directory, database, queue, and config file.

The database is a standard SQLite file you fully own. You can open it with any
SQLite tool (DB Browser, `sqlite3`, editor extensions) — the CLI and dashboard
are conveniences, not lock-in.

## The local dashboard

`afterwit serve` starts a dashboard for browsing your lessons. It is served by
a local HTTP server that is:

- **Bound to `127.0.0.1` only** — it is not reachable from other machines.
- **Read-only** — it never modifies your lessons.
- **Protected against DNS-rebinding** — incoming requests are validated by
  Host header.
- **Free of external assets** — the page loads no external fonts, scripts, or
  styles, so rendering it makes no third-party requests.

`afterwit report` produces the same view as a single self-contained HTML file
with the data inlined; it, too, references no external resources.

## Secrets and sensitive data

Session transcripts (Claude Code's own files) can contain sensitive values.
Afterwit is designed to keep those out of your lessons:

- The extraction prompt explicitly instructs the model **not** to copy secrets,
  API keys, tokens, passwords, or personal data into any lesson field.
- Afterwit stores only the distilled lessons, not the underlying transcript.

No automated filter is perfect. Before sharing lesson output anywhere (for
example, `afterwit list -v` or an exported `report`), review it to confirm it
contains nothing you would not want to share.

## Resurfacing lessons in new sessions

When a new Claude Code session starts, Afterwit reads your local lessons
database (read-only) and injects a short block of your most relevant recent
lessons into the session's context. This happens entirely on your machine: the
lessons come from your own local database and are provided to Claude as context
for that session. You can disable this at any time by setting
`"inject_enabled": false` in `config.json`.

## The bundled MCP server

Afterwit includes a local MCP server (`lessons`) that lets Claude answer
questions from your lessons database mid-session. It is **read-only, runs
locally, never writes to the database, and makes no network calls.**

## Your control over your data

- **Delete a single lesson:** `afterwit delete <id>`. Lessons are never
  auto-deleted; this is the only destructive operation Afterwit performs on its
  own data.
- **Delete everything:** remove the data directory that `afterwit paths`
  prints (default `~/.local/share/afterwit`, or `%LOCALAPPDATA%\afterwit` on
  Windows). That single removal wipes all Afterwit data.
- **Uninstall:** `/plugin uninstall afterwit`. Because the database lives
  outside the plugin directory, your lessons survive an uninstall — remove the
  data directory as well if you want them gone too.

## Auditability

Afterwit is a small set of dependency-free Python files you can read in one
sitting. To verify the claims above yourself:

```
grep -rn "urllib\|socket\|http" plugins/afterwit/src
```

This surfaces exactly one **outbound** call site (the loopback-only Ollama
backend) and one **inbound** one (the dashboard's local `http.server`). There
are no other network paths in the plugin.

## Changes to this policy

If Afterwit's data handling changes, this document and the
[CHANGELOG](CHANGELOG.md) will be updated in the same release. The effective
date at the top reflects the most recent revision.

## Contact

Questions about privacy or data handling: Lazar Trajkovic —
<lazartrajkovic1989@gmail.com>, or open an issue at
<https://github.com/laki889/afterwit>.
