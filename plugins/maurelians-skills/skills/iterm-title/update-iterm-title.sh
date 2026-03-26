#!/bin/bash
set -euo pipefail

# Update iTerm2 tab title mid-session.
# Usage: bash ~/.claude/hooks/update-iterm-title.sh "task description"
#
# Prepends "Claude: " and sets the iTerm2 user variable.
# Call this when the session's purpose becomes clear.

description="${1:-}"
if [ -z "$description" ]; then
  echo "Usage: update-iterm-title.sh <description>" >&2
  exit 1
fi

title="Claude: ${description}"

# Set iTerm2 user-defined variable via escape sequence.
title_b64=$(printf '%s' "$title" | base64)
printf '\033]1337;SetUserVar=%s=%s\007' "claudeTitle" "$title_b64"

echo "iTerm2 title set to: ${title}"
