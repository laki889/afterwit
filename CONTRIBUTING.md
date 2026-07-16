# Contributing to Afterwit

Thanks for looking under the hood — being read end-to-end is one of this
project's design goals.

## Ground rules (the privacy contract)

Afterwit's promise is "100% local, read every line." Changes must preserve:

1. **No new network egress.** The only outbound call is the distillation
   itself, to the user's own `claude` CLI or a loopback-validated Ollama.
   `grep -rn "urllib\|socket\|http" plugins/afterwit/src` should stay
   boring. The dashboard page must keep loading zero external assets.
2. **Stdlib only.** No pip dependencies, no native modules, no build step.
   Python 3.9 compatibility: use `from __future__ import annotations` in
   any file with `X | Y` type annotations.
3. **Readers never write.** SessionStart hook, dashboard, `report`, and the
   MCP server open the DB with `store.connect(readonly=True)`.
4. **Hooks never disturb a session.** `session_end.py` / `session_start.py`
   must stay instant, exception-swallowing, exit-0.
5. **User data outlives the plugin.** Nothing under `${CLAUDE_PLUGIN_ROOT}`
   may store state; everything lives in the `paths.data_dir()` tree.
   Lessons are never deleted except by explicit `afterwit delete`.

## Working on it

```
git clone <your fork> && cd afterwit
python3 -m unittest discover -s tests      # all tests, no setup needed
```

- `AFTERWIT_DATA_DIR=$(mktemp -d)` sandboxes any manual run.
- To test the plugin surface end-to-end inside Claude Code:
  `/plugin marketplace add /path/to/your/clone` then
  `/plugin install afterwit@afterwit`.
- Schema changes: bump `SCHEMA_VERSION` in `store.py` and add a stepwise
  migration in `_migrate` — existing users' databases must upgrade in place.
- The extraction prompt (`synth.EXTRACTION_PROMPT`) is the heart of the
  project. Changes to it should come with before/after samples from a real
  transcript in the PR description.
- Platform behavior (hook payloads, manifest formats, transcript JSONL) is
  documented in `docs/platform-notes.md` — re-verify against current Claude
  Code docs before relying on it, and update the file when it drifts.

## Tests

Every module has a test file under `tests/`; new behavior needs a test that
fails without it. The suite must stay dependency-free and fast (<10s).
