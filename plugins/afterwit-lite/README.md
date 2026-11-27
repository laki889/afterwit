# Afterwit Lite

**A lessons-learned logbook for your project, written by Claude when you ask.**

You solve a hard problem with Claude, and a month later you solve it again
because nobody wrote down what the real cause was. Afterwit Lite makes writing
it down a single command. Before you end a session that taught you something,
run `/afterwit-lite:reflect`. Claude distills the reusable lessons (root
causes, non-obvious gotchas, decisions worth repeating) into one Markdown file
in your project, and checks that file before re-solving a problem you have
already hit.

*Afterwit (n., archaic): wisdom that comes only after the event.*

## What you get

| Command | What it does |
|---|---|
| `/afterwit-lite:setup` | One-time setup: creates the lessons file and, only if you agree, tells future sessions where it is. |
| `/afterwit-lite:reflect` | Distills 0 to 3 lessons from the current session and appends them to the file. |
| `/afterwit-lite:search <query>` | Finds lessons that match your words. |
| `/afterwit-lite:review` | A short reflection on your lessons: recurring themes and what deserves a permanent fix. |

There is also a `lessons` skill that Claude uses on its own: when you ask
"have I hit this before?", or when the work looks like a problem the file
already covers, it checks the file first.

## How it works

Afterwit Lite is a set of instructions for Claude. It contains no code.

- **One file per project.** Lessons live in `.afterwit/lessons.md` at the root
  of your project. It is plain Markdown: read it, edit it, delete entries, or
  commit it so your team shares the same lessons.
- **Nothing happens on its own.** There are no hooks and no background
  processes. A lesson is written only when you run `reflect`, and each write
  goes through Claude's normal file-edit permission, like any other change to
  your project.
- **Quality over quantity.** Most sessions hold zero to three real lessons.
  Typos, one-off slips and generic advice are left out, and a lesson names the
  pattern ("N+1 query from lazy loading inside a loop"), not the incident.

## What it reads and writes

- **Reads:** `.afterwit/lessons.md` in the current project.
- **Writes:** `.afterwit/lessons.md`, when you run `reflect` or `setup`.
- **Writes only if you say yes during setup:** one line in the project's
  `CLAUDE.md` that points future sessions at the lessons file, and one line in
  `.gitignore` if you want the lessons kept out of version control.

It adds no data flow of its own. There are no servers, no accounts, no
telemetry and no network calls: distilling happens inside the Claude session
you are already having, under the same terms as the rest of that session.
Claude is told to keep secrets, keys, tokens and personal data out of the
lessons, but review the file before you share it. [PRIVACY.md](PRIVACY.md) has
the full statement.

## Afterwit Lite and Afterwit

Afterwit Lite is the instructions-only edition of
[Afterwit](https://github.com/laki889/afterwit). The full plugin captures
every session automatically, keeps a searchable database across all your
projects, and has a dashboard; it does that with hooks and local programs.
Afterwit Lite trades that automation for a plugin that is nothing but text.

## License

MIT. See [LICENSE](LICENSE).
