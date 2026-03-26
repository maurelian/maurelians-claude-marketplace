# maurelians-claude-marketplace

Personal Claude Code skills for [@maurelian](https://github.com/maurelian).

> **User-level install required.** These skills reference paths under `~/.claude/plugins/` and must be installed at user scope, not project scope.

## Install

```bash
claude plugin marketplace add https://github.com/maurelian/maurelians-claude-marketplace
claude plugin install maurelians-skills --scope user
```

## Skills

| Skill | Description |
|-------|-------------|
| `/address-pr <number>` | Address PR review comments — fetches unresolved threads, makes fixes, replies, and resolves |
| `/iterm-title <description>` | Set the iTerm2 tab title for the current session |
| `/set-topic <description>` | Set the status line task label (shown in Claude Code status bar) |
| `/setup-statusline` | One-time setup to configure the Claude Code status line |
