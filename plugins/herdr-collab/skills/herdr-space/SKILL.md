---
name: herdr-space
description: Create a new herdr space — top-level, or nested under the current one as a git worktree on its own branch — optionally with an agent working a task and a shell alongside it. Use when the user says "new workspace", "new space", "open a space in <dir>", "new child workspace", "sub workspace", "spin up a worktree", "nest a workspace under this one", "start an agent on a branch", or asks for a fresh place to work without leaving the current session.
---

# herdr space

Creates a new space in herdr's sidebar in one call: either a **top-level** space, or a
**child** indented beneath the current one.

## Top-level or child

Top-level is the default. Make a child only when the user asks for one — "child",
"sub workspace", "nested", "worktree", "on a branch", or names a branch or base.

The thing to understand about children: **herdr only nests worktree children.** A
child is always a real Git worktree on its own branch — there is no generic
parent/child relationship, no flag to nest two unrelated workspaces, and no call that
reparents an existing one. So a child means creating a branch and a checkout — a
write, not a view.

A child needs the current workspace to be inside a Git work tree. When it isn't, the
script does not fail: it creates a top-level space in the same directory instead and
says so (`"nesting": "top_level"` plus a `note`). `--branch` and `--base` are then
reported back under `ignored`. Read `nesting` in the summary before telling the user it
landed under the current one.

## Creating one

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/herdr-collab.py" space --label "notes"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/herdr-collab.py" space --cwd ~/Projects/other
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/herdr-collab.py" space --child \
  --branch feat/thing --task "port the retry logic to the new client"
```

Call it by that full path every time, not through a `$S` shorthand — the
auto-approve hook in `~/.claude/settings.json` matches on the script path.

A task alone is enough to get an agent, and it comes up running the same agent as the
session that asked for it.

Flags, all optional:

| flag | effect |
| --- | --- |
| `--child` | nest under the current workspace as a new worktree |
| `--branch NAME` | branch for the child's worktree; implies `--child`. herdr picks one if omitted |
| `--base REF` | branch the child off this ref instead of the current HEAD; implies `--child` |
| `--cwd DIR` | directory for a top-level space; defaults to this pane's cwd. Conflicts with `--child` |
| `--label TEXT` | sidebar label for the new space |
| `--agent [KIND]` | start an agent in the root pane. **Leave the kind off to get the same agent that is running this session** — name one (`claude`, `codex`, `pi`, …) only when the user asks for something different |
| `--task TEXT` | prompt to hand the agent once it is ready; implies `--agent`, so the kind is inherited unless given. Quote it as one argument |
| `--split` | add a shell pane beside the agent, in the same directory |
| `--focus` | switch to the new space; default is to leave focus where it is |

Prints a JSON summary — new `workspace`, its `nesting`, `cwd`, `root_pane`,
`shell_pane`, the `agent` block, and `branch` plus `parent_workspace` for a child. Read
the ids from it rather than guessing them.

**Don't ask first.** Creating the space is the request, so run it. For a child, pick a
branch name from the task when the user didn't give one, and say what was created
afterwards. Only stop to ask when the base ref is genuinely ambiguous — a repo with no
clear HEAD to branch from, or a user who named a base that doesn't resolve.

## Choosing the agent

Default to inheriting: pass `--agent` bare, or just `--task`, and the new space runs the
same kind as this session. Only pass `--agent KIND` when the user names a different
agent — "spin up a codex on this", say. Don't ask which agent to use; inheriting is the
answer unless they said otherwise.

If the session is not itself running under a detected agent, inheritance has nothing to
read and the script asks for `--agent KIND` explicitly.

## The trust prompt

A brand-new checkout, or any directory Claude Code has not opened before, lands on
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

A child (`nesting: "worktree_child"`):

```bash
herdr worktree remove --workspace <child>          # add --force if it has a live agent
```

That removes the checkout but leaves the branch. Say which of the two the user is asking
to discard before running anything.

A top-level space has no worktree, so it is just:

```bash
herdr workspace close <workspace>
```

## Notes

- A child's checkout lands under `worktrees.directory` from
  `~/.config/herdr/config.toml` (`~/.herdr/worktrees` by default), not inside the
  parent repo.
- `--split` runs before the agent starts, so a TUI agent launches at its final size
  instead of reflowing its whole buffer when the split arrives.
- If the agent fails to start for a real reason, the space still exists — the error
  names it and the right removal command for how it was created. Nothing is rolled back
  automatically, because that would delete a branch and a checkout.
