---
name: herdr-child
description: Create a child workspace nested under the current one in herdr's sidebar — a git worktree on its own branch, optionally with an agent working a task and a shell alongside it. Use when the user says "new child workspace", "sub workspace", "spin up a worktree", "nest a workspace under this one", "start an agent on a branch", or asks for a fresh branch to work in without leaving the current session.
---

# herdr child workspace

Creates the indented row beneath the current workspace in herdr's sidebar, in one call.

The thing to understand first: **herdr only nests worktree children.** A "sub workspace"
is always a real Git worktree on its own branch — there is no generic parent/child
relationship, no flag to nest two unrelated workspaces, and no call that reparents an
existing one. So this skill creates a branch and a checkout every time. That is a write,
not a view.

## Requirements

The current workspace must be inside a Git work tree. If it isn't, the script says so
and there is no fallback — a non-repo workspace can never have children.

## Creating one

`$S` below is the bundled script:

```bash
S="${CLAUDE_PLUGIN_ROOT}/scripts/herdr-collab.py"

python3 "$S" child --branch feat/thing --label "the thing"
```

The common case needs no kind at all — a task alone is enough, and the child comes up
running the same agent as the session that asked for it:

```bash
python3 "$S" child --branch feat/thing --task "port the retry logic to the new client"
```

Flags, all optional:

| flag | effect |
| --- | --- |
| `--branch NAME` | branch for the new worktree; herdr picks one if omitted |
| `--base REF` | branch off this ref instead of the current HEAD |
| `--label TEXT` | sidebar label for the child workspace |
| `--agent [KIND]` | start an agent in the child's root pane. **Leave the kind off to get the same agent that is running this session** — name one (`claude`, `codex`, `pi`, …) only when the user asks for something different |
| `--task TEXT` | prompt to hand the agent once it is ready; implies `--agent`, so the kind is inherited unless given. Quote it as one argument |
| `--split` | add a shell pane beside the agent, in the same checkout |
| `--focus` | switch to the child; default is to leave focus where it is |

Prints a JSON summary — child `workspace`, `branch`, `checkout` path, `root_pane`,
`shell_pane`, and the `agent` block. Read the ids from it rather than guessing them.

**Ask before running it.** It creates a branch and a working copy on disk. Confirm the
branch name and base with the user unless they already gave both.

## Choosing the agent

Default to inheriting: pass `--agent` bare, or just `--task`, and the child runs the
same kind as this session. Only pass `--agent KIND` when the user names a different
agent — "spin up a codex on this", say. Don't ask which agent to use; inheriting is the
answer unless they said otherwise.

If the session is not itself running under a detected agent, inheritance has nothing to
read and the script asks for `--agent KIND` explicitly.

## The trust prompt

A brand-new checkout is a folder the agent has never seen, so `--agent claude` lands on
Claude Code's *"Is this a project you trust?"* question and comes up `blocked`. This is
the normal path, not a failure — the agent is running and waiting on the user.

When that happens the summary carries `status: "blocked"` plus `task_pending`, and the
task is **not** delivered. Tell the user to answer the prompt in that pane, then send it:

```bash
herdr agent prompt <root_pane> '<the task>'
```

Never answer that prompt on the user's behalf by sending keys to the pane. It is a
security boundary and the answer is theirs.

## Cleaning up

```bash
herdr worktree remove --workspace <child>          # add --force if it has a live agent
```

That removes the checkout but leaves the branch. Say which of the two the user is asking
to discard before running anything.

## Notes

- The checkout lands under `worktrees.directory` from `~/.config/herdr/config.toml`
  (`~/.herdr/worktrees` by default), not inside the parent repo.
- `--split` runs before the agent starts, so a TUI agent launches at its final size
  instead of reflowing its whole buffer when the split arrives.
- If the agent fails to start for a real reason, the child workspace still exists — the
  error names it and the command to remove it. Nothing is rolled back automatically,
  because that would delete a branch and a checkout.
