# Verified Claude Code platform facts (v2.1.207, 2026-07)

Everything below was verified against the official docs and/or real data on
2026-07-13 while building afterwit. Re-verify against current docs before
relying on it for changes — these formats evolve.

## Hooks

- **SessionEnd** stdin payload: `{session_id, transcript_path, cwd,
  hook_event_name: "SessionEnd", why}` — the reason field is **`why`**, *not*
  `reason`. Values: `clear | resume | logout | prompt_input_exit |
  bypass_permissions_disabled | other`. Informational only (cannot block);
  default timeout 600s.
- **SessionStart** stdin payload includes `source: startup|resume|clear|compact`.
  To inject context, stdout must be JSON:
  `{"hookSpecificOutput": {"hookEventName": "SessionStart",
  "additionalContext": "..."}}` — plain stdout text is NOT injected.
- Plugin hooks live in `hooks/hooks.json` (auto-discovered). Env available to
  hook processes: `CLAUDE_PLUGIN_ROOT` (per-version install dir),
  `CLAUDE_PLUGIN_DATA` (survives updates but is **deleted on uninstall** —
  which is why afterwit uses an XDG dir instead), `CLAUDE_PROJECT_DIR`.
- A `Setup` hook exists but fires only on `claude --init/--init-only/
  --maintenance` — not a general post-install hook. Afterwit self-initializes
  at every entry point instead.

## Transcript JSONL (~/.claude/projects/<encoded-path>/<session>.jsonl)

- NOT one message per line. A streamed assistant message spans multiple lines
  sharing `message.id`, one content block per line, and chunks of one message
  can be **interleaved** with `tool_result` user lines (parallel tool calls).
  Thread order comes from `parentUuid`.
- User lines: `message.content` is a string OR an array with exactly one
  block (`text` or `tool_result`); `tool_result.content` is a string OR an
  array of typed blocks (`text`/`image`/`tool_reference`).
- Other line types to tolerate: `summary`, `system`, `attachment`,
  `queue-operation`, `ai-title`, `custom-title`, `last-prompt`, `mode`,
  `permission-mode`, `file-history-snapshot`, `frame-link`. Flags: `isMeta`
  (harness-injected), `isSidechain` (subagent lines, only in
  `<session-id>/subagents/**` sidecar files), `isApiErrorMessage` (synthetic
  assistant error records, `model: "<synthetic>"`).
- Files are appended live — tolerate a truncated final line. First line type
  is not stable.
- Transcripts are purged after `cleanupPeriodDays` (settings.json, default 30,
  min 1; cleanup runs at startup).

## Headless CLI

- `claude -p "<prompt>" --tools "" --output-format json
  --no-session-persistence` with the transcript piped via stdin (10MB cap).
  `--tools ""` disables all tools.
- stdout envelope: `{"type":"result","subtype":"success","is_error":bool,
  "result":"<text>","session_id":...,"usage":...}` — check `is_error` AND
  `subtype`.
- `-p` sessions fire hooks; afterwit sets `AFTERWIT_SYNC=1` in the subprocess
  env and its SessionEnd hook ignores runs where that's set (prevents
  self-capture). It also scrubs `CLAUDECODE`, `CLAUDE_CODE_ENTRYPOINT`,
  `CLAUDE_CODE_SSE_PORT` from the child env.

## Plugin & marketplace manifests

- `plugin.json` at `<plugin>/.claude-plugin/plugin.json`; only `name` is
  required (kebab-case). `commands/`, `skills/`, `hooks/hooks.json`,
  `.mcp.json`, `bin/` are auto-discovered at the plugin root ("don't put
  components inside .claude-plugin/"). `bin/` is added to the Bash tool PATH
  in sessions.
- `marketplace.json` at `<repo>/.claude-plugin/marketplace.json`; required:
  `name`, `owner{name}`, `plugins[]` (each: `name` + `source`; relative
  `"./plugins/afterwit"` resolves from the marketplace root). One repo can be
  both marketplace and plugin container. Reserved/official-sounding
  marketplace names are blocked (list in docs).
- Installed plugins are cached at
  `~/.claude/plugins/cache/<marketplace>/<plugin>/<version-hash>/` — the hash
  changes on update and orphaned versions are deleted after ~7 days, so never
  hardcode a cache path in cron jobs (README uses a glob).
- Install UX: `/plugin marketplace add <owner>/<repo>` then
  `/plugin install afterwit@afterwit`.

## Scheduling

No OS-level native scheduler for local plugin scripts. Options: cron/launchd
(README), Claude Code Desktop "scheduled tasks" (local, needs the app), or
cloud Routines (no local file access). In-session `/loop` is session-scoped.

## Naming (checked 2026-07-13)

"hindsight" is unusable: vectorize-io/hindsight (18k★ agent-memory platform
with an official Claude Code plugin `hindsight-memory`), a marketplace plugin
literally named `hindsight` (abix5), and `claude-hindsight` (transcript
viewer). "afterwit" was clean on GitHub, npm, and PyPI.
