#!/usr/bin/env bash
# Claude Code status line script
# Receives JSON session data on stdin, outputs a single-line status string.
# Per-session task labels stored in ~/.claude/statusline-tasks/<session_id>
#
# Setup: add to ~/.claude/settings.json:
#   "statusLine": {
#     "type": "command",
#     "command": "/path/to/this/statusline-command.sh"
#   }

set -euo pipefail

# ANSI colors
RESET="\033[0m"
BOLD="\033[1m"
DIM="\033[2m"
CYAN="\033[36m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
MAGENTA="\033[35m"
BLUE="\033[34m"

STATE_DIR="$HOME/.claude/statusline-tasks"

# Read session JSON from stdin
INPUT=$(cat)

# Extract fields using jq
MODEL=$(echo "$INPUT" | jq -r '.model.display_name // "?"')
CTX_PCT=$(echo "$INPUT" | jq -r '.context_window.used_percentage // 0' | awk '{printf "%.0f", $1}')
BRANCH=$(echo "$INPUT" | jq -r '.worktree.branch // empty' 2>/dev/null || true)
CWD=$(echo "$INPUT" | jq -r '.workspace.current_dir // .cwd // ""')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null || true)

# Write PID → session ID mapping so set-statusline-task.sh can find the session
if [[ -n "$SESSION_ID" ]]; then
  # Find Claude Code's PID by walking up from our PPID
  CLAUDE_PID=""
  pid=$PPID
  while [[ "$pid" -gt 1 ]]; do
    comm=$(ps -o comm= -p "$pid" 2>/dev/null) || break
    if [[ "$comm" == "claude" ]]; then
      CLAUDE_PID="$pid"
      break
    fi
    pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ') || break
  done
  if [[ -n "$CLAUDE_PID" ]]; then
    mkdir -p "$STATE_DIR"
    echo "$SESSION_ID" > "$STATE_DIR/.pid-$CLAUDE_PID"
  fi
fi

# Read per-session task label (keyed by session ID)
TASK=""
if [[ -n "$SESSION_ID" && -f "$STATE_DIR/$SESSION_ID" ]]; then
  TASK=$(cat "$STATE_DIR/$SESSION_ID" 2>/dev/null || true)
fi

# Read per-session focus worktree, fall back to detecting from CWD
WORKTREE_PATH=""
if [[ -n "$SESSION_ID" && -f "$STATE_DIR/$SESSION_ID.worktree" ]]; then
  WORKTREE_PATH=$(cat "$STATE_DIR/$SESSION_ID.worktree" 2>/dev/null || true)
fi
if [[ -z "$WORKTREE_PATH" && "$CWD" =~ (worktrees/[^/]+/[^/]+) ]]; then
  WORKTREE_PATH="${BASH_REMATCH[1]}"
fi

# Build status line
parts=()

# Task label first (bold cyan — the most important info)
if [[ -n "$TASK" ]]; then
  parts+=("${BOLD}${CYAN}${TASK}${RESET}")
fi

# Worktree path or branch
if [[ -n "$WORKTREE_PATH" ]]; then
  parts+=("${MAGENTA}${WORKTREE_PATH}${RESET}")
elif [[ -n "$BRANCH" ]]; then
  parts+=("${GREEN}${BRANCH}${RESET}")
fi

# Session ID (full, on its own line, dimmed)
SESSION_LINE=""
if [[ -n "$SESSION_ID" ]]; then
  SESSION_LINE="${DIM}${SESSION_ID}${RESET}"
fi

# Context usage with color thresholds
if (( CTX_PCT >= 80 )); then
  parts+=("${RED}${CTX_PCT}%${RESET}")
elif (( CTX_PCT >= 60 )); then
  parts+=("${YELLOW}${CTX_PCT}%${RESET}")
else
  parts+=("${DIM}${CTX_PCT}%${RESET}")
fi

# Model (claude orange, after context)
ORANGE="\033[38;5;172m"
parts+=("${ORANGE}${MODEL}${RESET}")

# Join with dimmed separator
SEP="${DIM} · ${RESET}"
result=""
for i in "${!parts[@]}"; do
  if (( i > 0 )); then
    result+="$SEP"
  fi
  result+="${parts[$i]}"
done

if [[ -n "$SESSION_LINE" ]]; then
  echo -e "$result\n$SESSION_LINE"
else
  echo -e "$result"
fi
