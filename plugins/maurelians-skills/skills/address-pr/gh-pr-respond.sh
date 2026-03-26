#!/usr/bin/env bash
# gh-pr-respond.sh — Reply to a PR review comment and optionally resolve the thread.
#
# Usage: gh-pr-respond.sh <pr-number> --comment-id <id> --body <text> [--resolve --thread-id <id>] [--repo <owner/repo>]
#
# Output (JSON to stdout, diagnostics to stderr):
# {
#   "pr": 1234,
#   "repo": "owner/repo",
#   "comment_id": 123456789,
#   "reply_posted": true,
#   "thread_resolved": true,
#   "reply_url": "https://github.com/..."
# }

set -euo pipefail

# ---------- argument parsing ----------
PR_NUMBER=""
COMMENT_ID=""
BODY=""
RESOLVE=false
THREAD_ID=""
REPO=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --comment-id) COMMENT_ID="$2"; shift 2 ;;
    --body)       BODY="$2"; shift 2 ;;
    --resolve)    RESOLVE=true; shift ;;
    --thread-id)  THREAD_ID="$2"; shift 2 ;;
    --repo)       REPO="$2"; shift 2 ;;
    -*)           echo "Unknown option: $1" >&2; exit 1 ;;
    *)
      if [[ -z "$PR_NUMBER" ]]; then
        PR_NUMBER="$1"
      else
        echo "Unexpected argument: $1" >&2; exit 1
      fi
      shift
      ;;
  esac
done

if [[ -z "$PR_NUMBER" || -z "$COMMENT_ID" || -z "$BODY" ]]; then
  echo "Usage: gh-pr-respond.sh <pr-number> --comment-id <id> --body <text> [--resolve --thread-id <id>] [--repo <owner/repo>]" >&2
  exit 1
fi

if [[ "$RESOLVE" == true && -z "$THREAD_ID" ]]; then
  echo "Error: --resolve requires --thread-id" >&2
  exit 1
fi

# ---------- detect repo if not provided ----------
if [[ -z "$REPO" ]]; then
  REPO=$(gh pr view "$PR_NUMBER" --json url --jq '.url' 2>/dev/null \
    | sed -n 's|https://github.com/\([^/]*/[^/]*\)/pull/.*|\1|p')
  if [[ -z "$REPO" ]]; then
    echo "Could not detect repo for PR #$PR_NUMBER. Use --repo <owner/repo>." >&2
    exit 1
  fi
fi

OWNER="${REPO%%/*}"
NAME="${REPO##*/}"

# ---------- post reply ----------
echo "Replying to comment $COMMENT_ID on PR #$PR_NUMBER in $REPO" >&2

REPLY_RAW=$(gh api --method POST \
  "repos/$OWNER/$NAME/pulls/$PR_NUMBER/comments/$COMMENT_ID/replies" \
  -f body="$BODY" 2>/dev/null) || {
  echo "Failed to post reply to comment $COMMENT_ID" >&2
  exit 1
}

REPLY_URL=$(echo "$REPLY_RAW" | jq -r '.html_url // empty')
echo "Reply posted: $REPLY_URL" >&2

# ---------- resolve thread if requested ----------
THREAD_RESOLVED=false
if [[ "$RESOLVE" == true ]]; then
  echo "Resolving thread $THREAD_ID" >&2

  RESOLVE_RAW=$(gh api graphql -f query="
  mutation {
    resolveReviewThread(input: {threadId: \"$THREAD_ID\"}) {
      thread { isResolved }
    }
  }" 2>/dev/null) || true

  if echo "$RESOLVE_RAW" | jq -e '.data.resolveReviewThread.thread.isResolved' >/dev/null 2>&1; then
    THREAD_RESOLVED=true
    echo "Thread resolved" >&2
  else
    echo "Warning: failed to resolve thread $THREAD_ID" >&2
  fi
fi

# ---------- output ----------
jq -n \
  --arg pr "$PR_NUMBER" \
  --arg repo "$REPO" \
  --arg comment_id "$COMMENT_ID" \
  --argjson reply_posted true \
  --argjson thread_resolved "$THREAD_RESOLVED" \
  --arg reply_url "$REPLY_URL" \
  '{
    pr: ($pr | tonumber),
    repo: $repo,
    comment_id: ($comment_id | tonumber),
    reply_posted: $reply_posted,
    thread_resolved: $thread_resolved,
    reply_url: $reply_url
  }'
