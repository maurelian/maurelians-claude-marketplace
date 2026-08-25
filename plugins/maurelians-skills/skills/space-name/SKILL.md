---
name: space-name
description: "Rename the current herdr space to describe this session"
argument-hint: "<description>"
---

# Set herdr Space Name

Rename the herdr space this session is running in, so the sidebar shows what the
session is about. Use when you know what the session is for, or when the user
asks to change the space name.

# CRITICAL REQUIREMENTS

- [CLAUDE TASK] Keep the description under 40 characters
- [CLAUDE TASK] Renaming affects the whole space, not just this pane or tab. If
  the space already has a name covering more than this session, ask before
  overwriting it.

## Usage

```
/space-name fix CI flakes
/space-name review PR #1234
/space-name                    (infers from current task)
```

## Steps

1. [CLAUDE TASK] Take the argument as the space name. If no argument is provided,
   infer a short description from the current task context.

2. [CLAUDE TASK] Run:

```bash
if [ -n "$HERDR_WORKSPACE_ID" ]; then \
  herdr workspace rename "$HERDR_WORKSPACE_ID" "<description>"; \
fi
```

   `HERDR_WORKSPACE_ID` is exported into every herdr pane, so no lookup is
   needed. The guard makes this a no-op outside herdr, exiting 0.

3. [CLAUDE TASK] Confirm the new name to the user. The command prints the updated
   workspace as JSON; the `label` field is the new name.

## Examples

| Input | Space renamed to |
|-------|------------------|
| `/space-name fix CI flakes` | `fix CI flakes` |
| `/space-name review PR #1234` | `review PR #1234` |
| `/space-name` (while working on auth) | `auth feature` (inferred) |

## Notes

Renaming preserves any workspace metadata tokens (such as a `$num` index pushed
by a plugin) — it only changes the label.
