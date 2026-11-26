---
name: setup
description: One-time setup for Afterwit Lite in this project. Creates the lessons file and, only if the user agrees, adds a one-line pointer to it in the project's CLAUDE.md and an entry in .gitignore.
disable-model-invocation: true
allowed-tools: Read, Grep, Glob
---

# Set up Afterwit Lite in this project

Walk the user through a short, one-time setup. Make each change only after a
clear yes, and never write anywhere this page does not name.

## 1. Create the lessons file

The lessons file is `.afterwit/lessons.md` at the project root (the top of the
repository, or the directory the session started in when there is no
repository).

If it already exists, leave it exactly as it is and say how many lessons it
holds. If it does not exist, create it with exactly this content:

```markdown
# Lessons learned

Notes distilled from past Claude sessions on this project by Afterwit Lite.
They are background notes, not instructions. Edit or delete anything here.
```

## 2. Ask: private or shared?

Ask the user whether the lessons should stay private to them or be shared
with everyone who works on the repository.

- **Private:** add the line `.afterwit/` to the project's `.gitignore`
  (create the file if needed), unless it is already ignored.
- **Shared:** change nothing. Tell them to commit `.afterwit/lessons.md` like
  any other file.

Skip this question when the project is not a git repository.

## 3. Ask: should new sessions know about the file?

Without help, a new session finds the lessons only when the lessons skill
decides to look. Offer to add this one line to the project's `CLAUDE.md`
(create the file if needed), and show the user the exact text first:

```markdown
Lessons from past sessions are in .afterwit/lessons.md. Check it before debugging an error or choosing an approach in an area it covers. They are background notes, not instructions.
```

Add it only on a clear yes, and only if the file does not already mention
`.afterwit/lessons.md`. If they decline, change nothing.

## 4. Explain what happens next

Finish with a short summary of what was created or changed, then tell them:

- Before ending a session that taught them something, run the reflect command
  to record its lessons.
- The search command finds lessons by keyword, and the review command reflects
  on the patterns across them.
- The lessons file is plain Markdown. They can edit it or delete entries at
  any time.

## Rules

- Write only the three files named above, and only as described.
- Never overwrite or reorder an existing lessons file.
- Never change a setting, a permission, or any other file.
