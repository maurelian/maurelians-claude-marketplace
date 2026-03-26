---
name: set-topic
description: Set the status line task label for the current session. Usage: /set-topic <description>
version: 1.0.0
---

# NON-NEGOTIABLE

- [CLAUDE TASK] Must run the set-statusline-task.sh script to persist the label
- [CLAUDE TASK] Must confirm the change to the user
- [CLAUDE TASK] Claude has no persistent shell state — bundle environment variable exports with commands using `&&`

# Set Topic

Set the status line task label to describe what this session is focused on.
The status line shows: task label, model, repo, worktree, and context usage %.

## Usage

```
/set-topic fix CI flakes
/set-topic review PR #1234
/set-topic clear        (clears the label)
/set-topic              (auto-generates from session context)
```

## Steps

1. [CLAUDE TASK] Find the setter script. Look in these locations (in order):
   - `scripts/hooks/set-statusline-task.sh` (relative to project root, for op-claude users)
   - The maurelians-skills plugin scripts directory
   - `~/.claude/hooks/set-statusline-task.sh`

2. [CLAUDE TASK] Determine the task label:
   - **If $ARGUMENTS is "clear"**: clear the label by running `bash <path>/set-statusline-task.sh ""`
   - **If $ARGUMENTS is provided** (anything other than "clear"): use it as-is
   - **If $ARGUMENTS is empty**: infer a short label (under 40 chars) from the current
     session context — what repo you're in, what task is underway, what the user last
     asked about. Examples: "fix CI flakes", "review PR #1234", "plan auth refactor".
     Do NOT clear the label or ask the user — just pick the best label you can.

3. [CLAUDE TASK] Run: `bash <path>/set-statusline-task.sh "<label>"`

4. [CLAUDE TASK] Set the worktree directory if applicable. If the session is working
   in a worktree (check for `worktrees/` in the current path or recent git context),
   also run: `bash <path>/set-statusline-task.sh --worktree "<relative-worktree-path>"`

5. [CLAUDE TASK] Confirm to the user what was set.

## Setup

To use the status line, add to your `~/.claude/settings.json`:

```json
"statusLine": {
  "type": "command",
  "command": "<path-to>/statusline-command.sh"
}
```

Both `statusline-command.sh` and `set-statusline-task.sh` are bundled in the
`scripts/` directory of this plugin. Copy or symlink them to a stable location.
