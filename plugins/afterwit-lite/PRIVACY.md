# Afterwit Lite privacy

Afterwit Lite is a set of instructions for Claude. It contains no code, runs
no servers, has no accounts and no telemetry, and makes no network requests.
Its author receives nothing from you: no usage data, no lessons, no contact
details.

This page covers the Afterwit Lite plugin only. The full Afterwit plugin has
its own privacy page in the repository root.

## What it reads

- **The current conversation,** when you run the reflect command. Claude
  already has that conversation; the plugin asks it to pick out the reusable
  lessons.
- **`.afterwit/lessons.md` in the current project,** when you search or
  review your lessons, or when Claude checks them before working on a problem
  the file covers.

## What it writes

- **`.afterwit/lessons.md` in the current project,** when you run the reflect
  or setup command.
- **Only if you say yes during setup:** one line in the project's `CLAUDE.md`
  that points later sessions at the lessons file, and one line in
  `.gitignore`.

It writes nothing else, and each write goes through Claude's normal file-edit
permission.

## Where your data goes

Nowhere new. Distilling lessons happens inside the Claude session you are
already having, so the conversation is handled by your Claude provider under
the terms that already apply to that session. Afterwit Lite adds no other
recipient and no other copy.

The lessons file stays in your project. If you commit it, it is shared with
everyone who can read that repository. Setup asks whether you want that, and
adds the file to `.gitignore` if you do not.

## What ends up in a lesson

A lesson records a problem, its root cause, what resolved it and the
takeaway. Claude is told never to copy a secret, key, token, password or
personal data into the file, and to refer to such things generically. That is
an instruction to a model, not a guarantee, so read the file before you share
or commit it.

Lessons are read back by Claude in later sessions on the same project. The
plugin tells Claude to treat them as notes about past work, never as
instructions.

## How long data is kept, and how to delete it

Lessons stay in `.afterwit/lessons.md` until you remove them. The file is
plain Markdown:

- delete an entry, or the whole `.afterwit` folder, at any time;
- remove the pointer line from `CLAUDE.md` and the `.afterwit/` line from
  `.gitignore` if setup added them;
- uninstall the plugin. Uninstalling does not delete your lessons file.

## Questions

Open an issue at <https://github.com/laki889/afterwit/issues>. Changes to this
page are recorded in the repository's history.
