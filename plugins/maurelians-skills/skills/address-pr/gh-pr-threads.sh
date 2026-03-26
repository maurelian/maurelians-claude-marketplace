#!/usr/bin/env bash
# gh-pr-threads.sh — Fetch unresolved PR review threads as structured JSON.
#
# Usage: gh-pr-threads.sh <pr-number> [--repo <owner/repo>]
#
# Output (JSON to stdout, diagnostics to stderr):
# {
#   "pr": 1234,
#   "repo": "owner/repo",
#   "viewer_login": "username",
#   "unresolved_threads": [ { "thread_id", "path", "line", "comments": [...] } ],
#   "total_unresolved": 3,
#   "total_resolved": 7
# }

set -euo pipefail

# ---------- argument parsing ----------
PR_NUMBER=""
REPO=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)   REPO="$2"; shift 2 ;;
    -*)       echo "Unknown option: $1" >&2; exit 1 ;;
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

if [[ -z "$PR_NUMBER" ]]; then
  echo "Usage: gh-pr-threads.sh <pr-number> [--repo <owner/repo>]" >&2
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
echo "Fetching review threads for PR #$PR_NUMBER in $REPO" >&2

# ---------- fetch viewer login ----------
VIEWER=$(gh api user --jq '.login' 2>/dev/null || echo "")
if [[ -z "$VIEWER" ]]; then
  echo "Warning: could not determine authenticated user. Own-comment filtering disabled." >&2
fi

# ---------- fetch review threads ----------
RAW=$(gh api graphql -f query="
query {
  repository(owner: \"$OWNER\", name: \"$NAME\") {
    pullRequest(number: $PR_NUMBER) {
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          path
          line
          comments(first: 10) {
            nodes {
              id
              databaseId
              body
              author { login }
            }
          }
        }
      }
    }
  }
}" 2>/dev/null) || {
  echo "Failed to fetch review threads for PR #$PR_NUMBER in $REPO" >&2
  exit 1
}

# ---------- check for errors ----------
ERRORS=$(echo "$RAW" | jq -r '.errors // empty')
if [[ -n "$ERRORS" ]]; then
  echo "GraphQL errors:" >&2
  echo "$RAW" | jq -r '.errors[].message' >&2
  exit 1
fi

PR_DATA=$(echo "$RAW" | jq '.data.repository.pullRequest')
if [[ "$PR_DATA" == "null" ]]; then
  echo "PR #$PR_NUMBER not found in $REPO" >&2
  exit 1
fi

# ---------- filter and assemble output ----------
echo "$RAW" | jq --arg pr "$PR_NUMBER" --arg repo "$REPO" --arg viewer "$VIEWER" '
  .data.repository.pullRequest.reviewThreads.nodes as $threads |
  {
    pr: ($pr | tonumber),
    repo: $repo,
    viewer_login: $viewer,
    unresolved_threads: [
      $threads[]
      | select(.isResolved == false)
      | {
          thread_id: .id,
          path: .path,
          line: .line,
          comments: [
            .comments.nodes[]
            | select($viewer == "" or .author.login != $viewer)
            | {
                id: .id,
                database_id: .databaseId,
                body: .body,
                author: .author.login
              }
          ]
        }
      | select(.comments | length > 0)
    ],
    total_unresolved: [ $threads[] | select(.isResolved == false) ] | length,
    total_resolved: [ $threads[] | select(.isResolved == true) ] | length
  }
'

UNRESOLVED=$(echo "$RAW" | jq '[ .data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false) ] | length')
RESOLVED=$(echo "$RAW" | jq '[ .data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == true) ] | length')
echo "Found $UNRESOLVED unresolved, $RESOLVED resolved threads" >&2
