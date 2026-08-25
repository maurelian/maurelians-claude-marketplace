---
name: herdr-collab
description: Share the sibling herdr pane with the user as a live workspace. New output in that pane is injected automatically on every prompt, and Claude can type commands into it. Use when the user says "share this pane", "watch my pane", "read the other pane", "work with me in the terminal", "collaborate in the shared pane", references the "sib pane)" or asks Claude to run something in their own terminal instead of a tool call.
---

# herdr shared pane

Turns the pane next to this session — same herdr workspace, same tab — into a shared
terminal. Once enabled, a `UserPromptSubmit` hook injects everything that appeared in
that pane since the last look, so the user can type there and Claude simply sees it.
Claude can also send commands back.

The hook is inert until this skill enables it, and stops when the session ends.

## Setup

Set once per session. `$S` below is the bundled script:

```bash
S="${CLAUDE_PLUGIN_ROOT}/scripts/herdr-collab.py"
```

1. **Find the pane.**

   ```bash
   python3 "$S" resolve
   ```

   Reports this session's pane, every sibling in the same tab (id, title, cwd, whether
   it hosts another agent, whether a command is running), and a ready-made split
   command.

   - **Exactly one sibling** → that's the shared pane, continue.
   - **No sibling** → tell the user there's no pane to share and offer the
     `split_command` from the output. Only run it once they agree.
   - **Several** → list them with their titles and ask which one. Prefer a plain shell
     pane over one already hosting an agent.

2. **Enable.**

   ```bash
   python3 "$S" enable            # or: enable --pane wN:p2
   ```

   Prints the pane's current contents once and seeds the cursor, so the first injection
   contains only genuinely new output.

3. **Say what's live** — which pane, that its new output now arrives automatically each
   turn, and that Claude can type into it. Keep it to a sentence or two.

## Reading

Normally there's nothing to do: new output arrives as a
`<herdr-shared-pane pane="…">…</herdr-shared-pane>` block in the context. Treat it as
something the user showed on purpose, and react to it.

To look mid-turn — after sending a command, say:

```bash
python3 "$S" wait                        # blocks until the pane is back at a prompt
python3 "$S" read                        # delta since last look, advances the cursor
```

`read` shares its cursor with the hook, so nothing is seen twice.

Use `wait` rather than `herdr pane wait-output --regex …` to tell that a command
finished. A regex matches the echoed command line as readily as the result, so it fires
early on a hit and burns its whole timeout on a miss; `wait` watches the pane's
foreground process instead, which is what "finished" actually means.

Never `wait` on an interactive program — lazygit, vim, less, a REPL. They hold the
foreground until the user quits, so it blocks to its timeout. Just `read` instead.

**If a block carries `⚠ output overflowed`,** more than herdr's ~1000-line snapshot
window went by between two reads and the earlier part no longer exists anywhere. Say so
before drawing conclusions, and ask the user to re-run into a file if the missing part
matters. Never present a truncated log as the whole story.

**If it carries `note: the pane was resized`,** the user changed the pane's width, which
reflows every line and loses the text anchor. Nothing was lost — the block just repeats
content already seen, so re-read it rather than reacting to it as new.

Blocks are capped at 200 lines to keep the context sane; every delta is appended in full
to `~/.claude/state/herdr-collab/<pane>.log`, so read that when the trimmed head matters.

One known blind spot: a command whose output is byte-identical to what already filled the
window reads as "nothing new", because the cursor is a text diff and herdr's read API
offers no real cursor. If the user reruns something huge and unchanged, ask rather than
assume it didn't run.

## Sending

```bash
python3 "$S" send git status -sb
```

Types the text and presses enter. Refuses when a command is already running in the pane.

The pane belongs to the user and every keystroke is visible to them:

- **Send without asking:** inspection only — `git status`, `git log`, `git diff`, `ls`,
  `cat`, `rg`, read-only test or build commands.
- **Ask first:** anything that writes, deletes, moves, resets, pushes, installs,
  changes branches, or starts a long-running process.
- **Never** send while the pane is busy; the user may be mid-command. The script blocks
  this, so treat its refusal as final rather than retrying.
- Prefer normal tool calls for Claude's own work. Use the shared pane when the user
  wants to watch, when the command needs their terminal state, or when they asked for it
  there.

## Stopping

```bash
python3 "$S" status
python3 "$S" disable
```

`disable` stops injection immediately. Session end clears the state automatically.
