#!/usr/bin/env bash
# Set per-session state shown in the Claude Code status line.
# Finds the Claude Code PID, looks up the session ID mapping, and writes
# the value keyed by session ID.
#
# Usage: bash set-statusline-task.sh "fix CI flakes"
#        bash set-statusline-task.sh --worktree "worktrees/optimism/feat-auth"
# Clear: bash set-statusline-task.sh ""
#        bash set-statusline-task.sh --worktree ""

set -euo pipefail

STATE_DIR="$HOME/.claude/statusline-tasks"

SUFFIX=""
if [[ "${1:-}" == "--worktree" ]]; then
  SUFFIX=".worktree"
  shift
fi
VALUE="${1:-}"

# Walk up process tree to find the Claude Code process PID
find_claude_pid() {
  local pid=$$
  while [[ "$pid" -gt 1 ]]; do
    local comm
    comm=$(ps -o comm= -p "$pid" 2>/dev/null) || break
    if [[ "$comm" == "claude" ]]; then
      echo "$pid"
      return
    fi
    pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ') || break
  done
  return 1
}

CLAUDE_PID=$(find_claude_pid) || exit 0

# Look up session ID from the PID mapping (written by statusline-command.sh)
PID_MAP="$STATE_DIR/.pid-$CLAUDE_PID"
if [[ ! -f "$PID_MAP" ]]; then
  SESSION_KEY="$CLAUDE_PID"
else
  SESSION_KEY=$(cat "$PID_MAP")
fi

mkdir -p "$STATE_DIR"

if [[ -z "$VALUE" ]]; then
  rm -f "$STATE_DIR/$SESSION_KEY$SUFFIX"
else
  echo "$VALUE" > "$STATE_DIR/$SESSION_KEY$SUFFIX"
fi
