---
name: address-pr
description: "Address PR review comments, make fixes, reply, and resolve"
argument-hint: "<pr-number>"
---

# Address PR Review Comments

Automates addressing pull request review feedback: analyze comments, make fixes, reply to explain changes, and resolve threads.

# CRITICAL REQUIREMENTS

- Claude executes all bash/gh commands using the Bash tool — never ask the user to run them
- NEVER auto-resolve comments where you disagree with the reviewer — always ask the user first via AskUserQuestion
- Filter out your own previous comments when analyzing review threads
- Commit and push changes before replying to review comments
- Claude has no persistent shell state — bundle environment variable exports with commands using `&&`

## Prerequisites

- Must have `gh` CLI authenticated
- Must be in a git repository with a GitHub remote

## Setup

1. [CLAUDE TASK] Resolve the skill's script directory. The helper scripts are co-located with this skill:

```bash
SKILL_DIR="$(dirname "$(find ~/.claude/plugins -path '*/address-pr/gh-pr-threads.sh' 2>/dev/null | head -1)" 2>/dev/null)"
if [[ -z "$SKILL_DIR" ]]; then
  echo "Error: address-pr scripts not found. Is the op-eng-skills plugin installed?" >&2
  exit 1
fi
```

Store `SKILL_DIR` for use in subsequent steps. All commands that use `$SKILL_DIR` must include the export inline (Claude has no persistent shell state).

## Step 1: Validate Input

**If $ARGUMENTS is empty:**
1. [CLAUDE TASK] Use AskUserQuestion to ask for the PR number

**If $ARGUMENTS is provided:**
1. [CLAUDE TASK] Extract and validate the PR number from $ARGUMENTS

## Step 2: Fetch PR Review Threads

1. [CLAUDE TASK] Run the thread-fetching script:

```bash
"$SKILL_DIR/gh-pr-threads.sh" PR_NUMBER
```

2. [CLAUDE TASK] Parse the JSON output:
   - `viewer_login` — your GitHub login (used for filtering in Step 3)
   - `unresolved_threads` — array of threads to address (own comments already filtered out)
   - `total_unresolved` — count of unresolved threads

3. [CLAUDE TASK] If `total_unresolved` is 0, inform the user and exit.

## Step 3: Analyze and Categorize Comments

For each unresolved thread from the script output:

1. [CLAUDE TASK] **Skip threads with no reviewer comments** — the script already filters out comments where `author` matches `viewer_login`. If a thread has 0 remaining comments, skip it.
2. [CLAUDE TASK] Read the comment body to understand the feedback.
3. [CLAUDE TASK] Identify the file path and line number from `path` and `line` fields.
4. [CLAUDE TASK] Read the relevant file section to understand the context.
5. [CLAUDE TASK] Categorize the type of feedback:
   - **Code change needed** — requires file modification
   - **Documentation** — needs comment/doc update
   - **Question** — requires explanation only, no code change
   - **Disagree/Won't fix** — ASK USER before responding

6. [CLAUDE TASK] Present a summary to the user showing the number of comments found, file paths affected, and a brief description of each comment.

**IMPORTANT**: For any comment where you disagree or think "won't fix" is appropriate, use AskUserQuestion to get user confirmation before replying. Never auto-resolve disagreements.

## Step 4: Address Categories of Comments Together

For each category of comment requiring action:

### 4a. Read the relevant file

1. [CLAUDE TASK] Use the Read tool to understand the context around the specified line.

### 4b. Make the fix

1. [CLAUDE TASK] Use the Edit tool to make the necessary changes based on the feedback. Give the user a summary of the comment(s) being addressed.

### 4c. Commit the work

1. [CLAUDE TASK] Stage all changed files with `git add`.
2. [CLAUDE TASK] Create a commit using conventional commits format.
3. [CLAUDE TASK] Push the changes to the remote branch.

### 4d. Reply to the comment and optionally resolve it

1. [CLAUDE TASK] Tell the user: "Now addressing https://github.com/{owner}/{repo}/pull/PR_NUMBER#discussion_r{COMMENT_DB_ID}"

2. [CLAUDE TASK] Run the response script:

```bash
"$SKILL_DIR/gh-pr-respond.sh" PR_NUMBER \
  --comment-id COMMENT_DB_ID \
  --body 'Fixed in COMMIT_SHA: [explanation of what was changed and why]' \
  --resolve --thread-id "THREAD_NODE_ID"
```

3. [CLAUDE TASK] Check the JSON output for `reply_posted` and `thread_resolved` status. If thread resolution failed, log it and continue to the next comment.

## Step 5: Summary

1. [CLAUDE TASK] Present a summary to the user:

- Number of comments addressed
- Files modified
- Commit hash created
- Comments that were NOT addressed (with reasons)
- Link to the PR

## Error Handling

- If `gh` CLI is not authenticated, instruct user to run `gh auth login`
- If PR number is invalid, show error and ask for correct number
- If a thread fails to resolve, log the error but continue with other threads
- If commit fails, show the error and suggest manual resolution
