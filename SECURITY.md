# Security policy

Afterwit runs on your machine with your permissions: two hooks, a local MCP
server and a CLI, all plain Python you can read. A flaw in any of them is
worth reporting.

## Supported versions

Fixes go into the latest release only. Check yours with `afterwit --version`
or `claude plugin list`.

## Reporting a vulnerability

Please don't post the details in a public issue.

1. Use the **Report a vulnerability** button on this repository's
   [Security tab](https://github.com/laki889/afterwit/security) if it is shown.
   That opens a private report only the maintainer can read.
2. If the button isn't there, open an issue titled "Security report" that
   says only that you have something to report, with no details. The
   maintainer will arrange a private channel.

A useful report says which version you ran, what you did, what happened and
what you expected. A proof of concept helps but isn't required.

This is a one-person project, so there is no guaranteed response time. Every
report gets read, and a confirmed problem gets a fix, a release and credit in
the changelog unless you'd rather not be named.

## What counts

Anything that breaks one of the promises in [PRIVACY.md](PRIVACY.md) or the
README is in scope. For example:

- Afterwit sending data anywhere other than the backend you configured (your
  own `claude` CLI, or a loopback Ollama server), or sending it without you
  running `sync`.
- A hook, the MCP server or the dashboard doing more than it says: opening a
  network connection, starting another program, or writing outside the data
  directory.
- The dashboard being reachable from another machine or another website.
- Text inside a session transcript steering the distillation step, or a
  stored lesson that carries instructions into later sessions.
- A secret from a transcript ending up in a stored lesson.

Bugs that aren't security problems belong in the normal
[issue tracker](https://github.com/laki889/afterwit/issues).
