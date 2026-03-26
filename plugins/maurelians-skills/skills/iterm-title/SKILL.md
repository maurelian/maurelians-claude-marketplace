---
name: iterm-title
description: "Set the iTerm2 tab title for this session"
argument-hint: "<description>"
---

# Set iTerm2 Tab Title

Set the iTerm2 tab title for this Claude Code session. Use when you know what the session is about, or when the user asks to change the tab title.

# CRITICAL REQUIREMENTS

- [CLAUDE TASK] Must run the update-iterm-title.sh script — do not use raw escape sequences
- [CLAUDE TASK] Keep the description under 40 characters

## Usage

```
/iterm-title fix CI flakes
/iterm-title review PR #1234
/iterm-title                   (infers from current task)
```

## Steps

1. [CLAUDE TASK] Take the argument as the title description. If no argument is provided, infer a short description from the current task context.

2. [CLAUDE TASK] Run the co-located script. The script is at `update-iterm-title.sh` relative to this skill's base directory:

```bash
bash ~/.claude/plugins/marketplaces/maurelians-claude-marketplace/plugins/maurelians-skills/skills/iterm-title/update-iterm-title.sh "<description>"
```

3. [CLAUDE TASK] Confirm the title was set.

## Examples

| Input | Title set |
|-------|-----------|
| `/iterm-title fix CI flakes` | `Claude: fix CI flakes` |
| `/iterm-title review PR #1234` | `Claude: review PR #1234` |
| `/iterm-title` (while working on auth) | `Claude: auth feature` (inferred) |
