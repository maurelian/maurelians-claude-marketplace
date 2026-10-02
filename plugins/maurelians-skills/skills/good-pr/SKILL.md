---
name: good-pr
description: "Prepare a PR for review: clean history, minimal changes, a reviewer-oriented description, and a self-review before requesting review. Use when opening a PR, cleaning one up, or before marking it ready or requesting review."
argument-hint: "[pr-number]"
---

# Good PR

Apply these principles to the PR (number from the argument, else `gh pr view` on the
current branch). Fix what you can, ask before rewriting history or posting anything.

## Principles

- Keep commit history clean. Atomic commits (not all tests need to be passing, but
  changes should be combined by motivation). Collapse fix-then-undo chains. OK to
  force push with lease in order to get this property.
- Smallest change that works. Prefer adjusting a value or adding a guard over
  refactoring logic, and keep the existing structure when possible.
- A proportional description that tells reviewers how to review: which links to use,
  and what to check in the mechanical commit.
- Don't drop useful context. Keep existing explanatory comments unless wrong. Comments
  should be evergreen, describe the current code, not what changed.

## Workflow

1. **Check the PR against the principles.** `git log --oneline <base>..HEAD` and the
   diff. Propose a regrouping if needed (back up the branch first, keep the final tree
   identical, `--force-with-lease=<branch>:<old-sha>`). Isolate mechanical churn such
   as formatter output in its own commit.
2. **Self-review before requesting review.** Spawn a subagent with `model: "fable"`
   to review the PR diff against the principles above and for correctness. It must
   return numbered comments, each with a link to the location in the PR diff view:
   `https://github.com/<owner>/<repo>/pull/<n>/files#diff-<sha256 of path>R<line>`
   (`L<line>` for removed lines). Relay the list to the user as-is, numbered.
3. **Offer explanatory comments.** For changes a reviewer would ask about, draft short
   comments and offer to post them as a pending review (one `POST
   /repos/<owner>/<repo>/pulls/<n>/reviews` with `comments[]` and no `event`), so the
   user can edit and submit it. Show the drafts before posting.
