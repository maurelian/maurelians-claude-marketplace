---
name: setup-statusline
description: Configure the Claude Code status line to show task label, model, repo, worktree, session ID, and context usage. Copies scripts and updates settings.json.
version: 1.0.0
---

# NON-NEGOTIABLE

- [CLAUDE TASK] Must not overwrite an existing statusline config without user confirmation
- [CLAUDE TASK] Must verify the script is executable and working before confirming success
- [CLAUDE TASK] Must not modify any file outside ~/.claude/ without explicit permission

# Setup Statusline

Configure the Claude Code status line to show session context at a glance:
task label, model, repo/worktree, session ID, and context usage %.

## Steps

1. [CLAUDE TASK] Find the statusline scripts. Look for `statusline-command.sh` and
   `set-statusline-task.sh` in these locations (in order):
   - The op-eng-skills plugin: search for files named `statusline-command.sh` under
     any directory matching `*/op-eng-skills/scripts/`
   - The current project: `scripts/hooks/statusline-command.sh`
   - `~/.claude/statusline-command.sh` (already installed)

2. [CLAUDE TASK] Copy both scripts to `~/.claude/hooks/`:
   - `~/.claude/hooks/statusline-command.sh`
   - `~/.claude/hooks/set-statusline-task.sh`

   Make both executable with `chmod +x`.

3. [CLAUDE TASK] Read `~/.claude/settings.json`. Check if a `statusLine` field
   already exists.

4. [USER REVIEW] If a statusline config already exists, show the user what it
   currently is and ask if they want to replace it. If no existing config, proceed.

5. [CLAUDE TASK] Update `~/.claude/settings.json` to add or replace the statusLine
   config:
   ```json
   "statusLine": {
     "type": "command",
     "command": "~/.claude/hooks/statusline-command.sh"
   }
   ```

6. [CLAUDE TASK] Verify the script works by running a test:
   ```bash
   echo '{"model":{"display_name":"Test"},"context_window":{"used_percentage":42}}' \
     | ~/.claude/hooks/statusline-command.sh
   ```
   Confirm the output looks correct.

7. [CLAUDE TASK] Tell the user:
   - The status line is now configured and will appear after the next assistant message
   - Use `/set-topic <description>` to set a task label for the current session
   - The task label, model, repo, worktree, session ID, and context % update automatically
