---
name: herdr-archive
description: Archive a herdr space — save its tabs, split layout, pane directories and agent conversations to a JSON file, then close it — or restore an archived space later with its agents resumed. Use when the user says "archive this space", "archive this workspace", "park this space", "put this away for later", "restore an archived space", "bring back <space>", "what spaces have I archived", or wants to close a space without losing its agent sessions.
---

# herdr archive

herdr has no undo for closing a space. This archives one to a JSON file instead, so it
can be rebuilt later in any session.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/hws-archive.py" archive [--force] [WORKSPACE_ID]
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/hws-archive.py" list
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/hws-archive.py" restore FILE
```

Archives live in `~/.config/herdr/archive/`. A restored archive moves to
`archive/restored/`, so it is never restored twice.

## What survives

Kept: the space label, tab labels, the exact split tree and ratios, each pane's
directory and label, which tab was active, and each agent's native session id.

Lost: running shells, servers, scrollback. Restore resumes each agent pane with its own
resume command (`claude --resume <id>`, `codex resume <id>`, `pi --session <path>`, …)
and leaves every other pane as a fresh shell in its old directory. An agent with no
known resume command also gets a plain shell, with a note on stderr.

## Archiving

`archive` defaults to `$HERDR_WORKSPACE_ID`, the space this session runs in. **That
closes your own pane** — the command's output is the last thing you see. So say what
you are about to archive *before* running it, and run it last.

To archive a different space, pass its id (`herdr workspace list` to find it).

It refuses while any agent in the space is `working`, naming the panes. Pass `--force`
only when the user has said to archive anyway; the interrupted turn is lost.

A zoomed tab cannot be archived — the layout is unreadable while zoomed. Ask the user
to unzoom it.

## Restoring

Run `list` first. Each line is tab-separated: path, archived time, label, tab count,
agents, directory, newest first. Pick the file whose label matches what the user asked
for; if several match, or none do, show them the candidates and ask.

`restore` rebuilds the space in the **current** session, focuses it, and prints its new
id. A child space comes back as a top-level one.

Any Claude pane in a directory Claude Code has not trusted yet stops at the *"Is this a
project you trust?"* prompt. Tell the user; never answer it for them.

## Notes

- Call the script by its full `${CLAUDE_PLUGIN_ROOT}` path every time, as with
  `herdr-collab.py`, so path-based permission rules keep matching.
- The archive format carries `"version": 1`; `restore` rejects anything else.
