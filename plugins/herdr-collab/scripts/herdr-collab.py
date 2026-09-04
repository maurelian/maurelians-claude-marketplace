#!/usr/bin/env python3
"""Shared-pane collaboration between a Claude Code session and its sibling herdr pane.

Subcommands: resolve, child, enable, read, send, wait, status, disable, hook, cleanup.
The `hook` subcommand is wired to UserPromptSubmit and injects output the agent
has not seen yet; it stays silent unless `enable` has written a state file.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

STATE_DIR = os.path.join(
    os.environ.get("CLAUDE_CONFIG_DIR", os.path.expanduser("~/.claude")),
    "state",
    "herdr-collab",
)
READ_SOURCE = "recent-unwrapped"
READ_LINES = "2000"
MAX_DELTA_LINES = 200
MAX_DELTA_CHARS = 8000
STALE_AFTER_SECONDS = 12 * 60 * 60
OVERFLOW_WARNING = (
    "⚠ output overflowed herdr's snapshot window — earlier lines are lost "
    "and cannot be recovered"
)
REDRAW_NOTICE = (
    "note: the pane was resized, which reflows every line and loses the anchor. "
    "Nothing was lost; this is the current view, most of it already seen"
)
REDRAW_TAIL_LINES = 20
WAIT_GRACE_SECONDS = 1.0
WAIT_POLL_SECONDS = 0.3
WAIT_TIMEOUT_SECONDS = 120.0
CHILD_SPLIT_RATIO = "0.4"


class Failure(Exception):
    """Condition to report to the caller rather than a crash."""


def herdr_bin():
    found = shutil.which("herdr")
    if found:
        return found
    for candidate in ("/opt/homebrew/bin/herdr", "/usr/local/bin/herdr"):
        if os.access(candidate, os.X_OK):
            return candidate
    raise Failure("herdr is not on PATH")


def herdr(*args, check=True):
    proc = subprocess.run(
        [herdr_bin(), *args], capture_output=True, text=True, timeout=10
    )
    if check and proc.returncode != 0:
        raise Failure(
            f"herdr {' '.join(args)} failed: {(proc.stderr or proc.stdout).strip()}"
        )
    return proc.stdout


def herdr_json(*args):
    payload = json.loads(herdr(*args))
    if "error" in payload:
        raise Failure(f"herdr {' '.join(args)}: {payload['error'].get('message')}")
    return payload["result"]


def agent_pane_id():
    pane = os.environ.get("HERDR_PANE_ID")
    if not pane:
        raise Failure(
            "HERDR_PANE_ID is unset — this session is not running inside a herdr pane"
        )
    return pane


def state_path(pane_id):
    return os.path.join(STATE_DIR, pane_id.replace(":", "-") + ".json")


def log_path(pane_id):
    return os.path.join(STATE_DIR, pane_id.replace(":", "-") + ".log")


def load_state(pane_id):
    try:
        with open(state_path(pane_id)) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def save_state(state):
    os.makedirs(STATE_DIR, exist_ok=True)
    path = state_path(state["agent_pane"])
    tmp = path + ".tmp"
    with open(tmp, "w") as handle:
        json.dump(state, handle)
    os.replace(tmp, path)


def clear_state(pane_id):
    for path in (state_path(pane_id), state_path(pane_id) + ".tmp"):
        try:
            os.remove(path)
        except OSError:
            pass


def panes():
    return herdr_json("pane", "list")["panes"]


def siblings(pane_id):
    """Panes sharing this pane's tab, nearest-neighbour semantics for the skill."""
    all_panes = panes()
    me = next((p for p in all_panes if p["pane_id"] == pane_id), None)
    if me is None:
        raise Failure(f"pane {pane_id} is not in the current herdr session")
    return me, [
        p
        for p in all_panes
        if p["tab_id"] == me["tab_id"] and p["pane_id"] != pane_id
    ]


def workspace_of(pane_id):
    return herdr_json("pane", "get", pane_id)["pane"]["workspace_id"]


def agent_name(*candidates):
    """First candidate herdr will accept: lowercase, [a-z0-9_-], starting with a letter."""
    for candidate in candidates:
        if not candidate:
            continue
        slug = "".join(
            char if char.isalnum() or char in "-_" else "-"
            for char in candidate.lower()
        ).strip("-")
        slug = slug[:32].rstrip("-")
        while slug and not slug[0].isalpha():
            slug = slug[1:]
        if slug:
            return slug
    return "agent"


def agent_status(pane_id):
    """Reported status of the agent in a pane, or None when no agent is detected."""
    try:
        return herdr_json("agent", "get", pane_id)["agent"].get("agent_status")
    except Failure:
        return None


def own_agent_kind():
    """Agent kind running this session, so a child defaults to the same kind as its parent."""
    try:
        kind = herdr_json("agent", "get", agent_pane_id())["agent"].get("agent")
    except Failure:
        kind = None
    if not kind:
        raise Failure(
            "could not tell which agent is running this session, so there is no kind "
            "to inherit — pass --agent KIND"
        )
    return kind


def opt_flag(argv, name):
    """(present, value) for a flag whose value may be left off to be inferred."""
    if name not in argv:
        return False, None
    index = argv.index(name) + 1
    if index < len(argv) and not argv[index].startswith("--"):
        return True, argv[index]
    return True, None


def flag_value(argv, name):
    """Value following `name`, or None. Matches the ad-hoc parsing the other commands use."""
    if name not in argv:
        return None
    index = argv.index(name) + 1
    if index >= len(argv):
        raise Failure(f"{name} needs a value")
    return argv[index]


def foreground_command(pane_id):
    """Command occupying the pane, or None when it is sitting at the shell prompt."""
    info = herdr_json("pane", "process-info", "--pane", pane_id)["process_info"]
    if info.get("foreground_process_group_id") == info.get("shell_pid"):
        return None
    running = info.get("foreground_processes") or []
    for proc in running:
        if proc.get("pid") != info.get("shell_pid"):
            return proc.get("cmdline") or proc.get("name")
    return running[0].get("cmdline") if running else "unknown command"


def pane_width(pane_id):
    """Column count, which the text anchor depends on: a resize redraws the whole pane."""
    layout = herdr_json("pane", "layout", "--pane", pane_id)["layout"]
    for pane in layout.get("panes", []):
        if pane["pane_id"] == pane_id:
            return pane["rect"]["width"]
    return None


def snapshot(pane_id):
    text = herdr("pane", "read", pane_id, "--source", READ_SOURCE, "--lines", READ_LINES)
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    return lines


def delta(prev, new):
    """New lines in `new`, plus whether the snapshot window scrolled past unseen output.

    The pane is an append-only window anchored to the newest output, so whatever
    survives of the previous view is flush with the top of the next snapshot and the
    longest such overlap is the frontier. The previous view's last line is excluded
    from the overlap because the shell rewrites it in place as the user types; it gets
    re-emitted once, carrying the command they typed onto it.

    No overlap at all means the previous view scrolled away entirely and output between
    the two reads is unrecoverable.
    """
    if len(prev) < 2 or not new:
        return new, False
    if prev == new:
        return [], False
    stable = prev[:-1]
    for size in range(min(len(stable), len(new)), 0, -1):
        if new[:size] == stable[-size:]:
            return new[size:], False
    return new, True


def truncate(lines):
    """Trim from the head so the tail — the most recent output — always survives."""
    truncated = False
    if len(lines) > MAX_DELTA_LINES:
        lines = lines[-MAX_DELTA_LINES:]
        truncated = True
    while lines and len("\n".join(lines)) > MAX_DELTA_CHARS:
        lines = lines[1:]
        truncated = True
    if truncated:
        lines = ["[…earlier lines trimmed; see the herdr-collab log…]"] + lines
    return lines


def append_log(pane_id, lines):
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(log_path(pane_id), "a") as handle:
            handle.write(f"\n--- {stamp} ---\n")
            handle.write("\n".join(lines) + "\n")
    except OSError:
        pass


def render(shared, lines, notice):
    body = "\n".join(truncate(lines))
    if notice:
        body = notice + "\n" + body
    return (
        f'<herdr-shared-pane pane="{shared["pane_id"]}" cwd="{shared.get("cwd", "")}">\n'
        f"{body}\n"
        "</herdr-shared-pane>"
    )


def collect(state, shared):
    """Delta since the last read, advancing the stored cursor."""
    pane_id = shared["pane_id"]
    lines = snapshot(pane_id)
    width = pane_width(pane_id)
    new_lines, missed = delta(state.get("snapshot") or [], lines)
    notice = None
    if missed:
        # A resize reflows the whole pane, so losing the anchor says nothing about
        # whether output was actually lost. Re-showing the whole view would be noise,
        # but the tail still carries anything that ran alongside the resize.
        if width != state.get("width"):
            notice = REDRAW_NOTICE
            new_lines = new_lines[-REDRAW_TAIL_LINES:]
        else:
            notice = OVERFLOW_WARNING
    state["snapshot"] = lines
    state["width"] = width
    save_state(state)
    if new_lines:
        append_log(state["agent_pane"], new_lines)
    return new_lines, notice


def require_enabled(pane_id):
    state = load_state(pane_id)
    if not state:
        raise Failure(
            "shared-pane collaboration is not enabled — run the herdr-collab skill first"
        )
    return state


def resolve_shared(state):
    _, sibs = siblings(state["agent_pane"])
    shared = next((p for p in sibs if p["pane_id"] == state["shared_pane"]), None)
    if shared is None:
        raise Failure(f"shared pane {state['shared_pane']} is gone")
    return shared


# --- subcommands ---------------------------------------------------------------


def cmd_resolve(_argv):
    pane_id = agent_pane_id()
    me, sibs = siblings(pane_id)
    print(
        json.dumps(
            {
                "agent_pane": pane_id,
                "tab": me["tab_id"],
                "workspace": me["workspace_id"],
                "cwd": me.get("cwd"),
                "enabled": load_state(pane_id) is not None,
                "siblings": [
                    {
                        "pane_id": p["pane_id"],
                        "title": p.get("terminal_title_stripped"),
                        "cwd": p.get("cwd"),
                        "hosts_agent": p.get("agent"),
                        "busy": foreground_command(p["pane_id"]),
                    }
                    for p in sibs
                ],
                "split_command": (
                    f"herdr pane split {pane_id} --direction right --ratio 0.4 "
                    f"--no-focus --cwd {me.get('cwd', '.')}"
                ),
            },
            indent=2,
        )
    )


def cmd_child(argv):
    """Create a worktree child of this workspace, optionally with an agent and a shell.

    herdr only indents worktree children in the sidebar, so a "sub workspace" is always
    a real Git worktree on its own branch — there is no way to nest two unrelated
    workspaces, and no call that reparents an existing one.
    """
    pane_id = agent_pane_id()
    workspace = workspace_of(pane_id)

    branch = flag_value(argv, "--branch")
    base = flag_value(argv, "--base")
    label = flag_value(argv, "--label")
    want_agent, kind = opt_flag(argv, "--agent")
    task = flag_value(argv, "--task")
    want_split = "--split" in argv
    focus = "--focus" in argv

    # A task is only ever for an agent, so asking for one implies asking for the other.
    if task:
        want_agent = True
    # Default to whatever is running this session: a child of a Claude session should be
    # another Claude unless the user says otherwise.
    if want_agent and not kind:
        kind = own_agent_kind()

    args = ["worktree", "create", "--workspace", workspace]
    for name, value in (("--branch", branch), ("--base", base), ("--label", label)):
        if value:
            args += [name, value]
    args.append("--focus" if focus else "--no-focus")

    try:
        created = herdr_json(*args)
    except Failure as err:
        if "Git work tree" in str(err):
            raise Failure(
                f"workspace {workspace} is not inside a Git work tree, so it cannot "
                "parent a child — herdr nests worktree children only"
            ) from err
        raise

    root = created["root_pane"]["pane_id"]
    checkout = created["worktree"]["path"]
    summary = {
        "workspace": created["workspace"]["workspace_id"],
        "label": created["workspace"]["label"],
        "branch": created["worktree"]["branch"],
        "checkout": checkout,
        "root_pane": root,
        "parent_workspace": workspace,
    }

    # Split first: a TUI agent launched at its final size avoids the full-buffer reflow
    # that splitting afterwards would force on it.
    if want_split:
        split = herdr_json(
            "pane", "split", root, "--direction", "right",
            "--ratio", CHILD_SPLIT_RATIO, "--no-focus", "--cwd", checkout,
        )
        summary["shell_pane"] = split["pane"]["pane_id"]

    if want_agent:
        # The pane id doubles as an agent target, which sidesteps having to invent a
        # unique agent name just to prompt the thing we already have a handle on.
        name = agent_name(label, branch, summary["workspace"])
        try:
            herdr("agent", "start", name, "--kind", kind, "--pane", root)
        except Failure as err:
            # A fresh checkout is a folder the agent has never seen, so Claude Code
            # opens its trust question and `agent start` reports it as not ready. The
            # agent is up and waiting on the user, which is not a failure to create.
            if agent_status(root) is None:
                # The worktree is already on disk by now. Rolling it back would delete
                # a real branch and checkout, so report what exists instead.
                raise Failure(
                    f"{err}\nthe child workspace was still created: "
                    f"{summary['workspace']} at {checkout} — remove it with "
                    f"`herdr worktree remove --workspace {summary['workspace']}`"
                ) from err

        status = agent_status(root)
        summary["agent"] = {"kind": kind, "name": name, "pane": root, "status": status}
        if task:
            if status == "blocked":
                summary["agent"]["task_pending"] = task
                summary["agent"]["note"] = (
                    "agent is blocked on a question in its pane and cannot take the "
                    f"task yet; answer it, then run `herdr agent prompt {root} "
                    "'<task>'`"
                )
            else:
                herdr("agent", "prompt", root, task)
                summary["agent"]["task"] = task

    print(json.dumps(summary, indent=2))


def cmd_enable(argv):
    pane_id = agent_pane_id()
    _, sibs = siblings(pane_id)
    wanted = None
    if "--pane" in argv:
        wanted = argv[argv.index("--pane") + 1]
        if not any(p["pane_id"] == wanted for p in sibs):
            raise Failure(f"{wanted} is not a pane in this tab")
    elif len(sibs) == 1:
        wanted = sibs[0]["pane_id"]
    elif not sibs:
        raise Failure(
            "no other pane in this tab — create one with `herdr pane split` first"
        )
    else:
        ids = ", ".join(p["pane_id"] for p in sibs)
        raise Failure(f"several panes in this tab ({ids}) — pass --pane <id>")

    shared = next(p for p in sibs if p["pane_id"] == wanted)
    lines = snapshot(wanted)
    save_state(
        {
            "version": 1,
            "agent_pane": pane_id,
            "shared_pane": wanted,
            "enabled_at": time.time(),
            "snapshot": lines,
            "width": pane_width(wanted),
        }
    )
    print(f"shared pane: {wanted} ({shared.get('terminal_title_stripped')})")
    print(f"cwd: {shared.get('cwd')}")
    print("new output will be injected automatically after each user prompt.")
    if lines:
        print("\ncurrent contents:")
        print("\n".join(truncate(lines)))


def cmd_read(_argv):
    pane_id = agent_pane_id()
    state = require_enabled(pane_id)
    shared = resolve_shared(state)
    lines, notice = collect(state, shared)
    print(render(shared, lines, notice) if lines else "no new output")


def cmd_wait(argv):
    """Block until the pane is back at its shell prompt."""
    timeout = WAIT_TIMEOUT_SECONDS
    if "--timeout" in argv:
        timeout = float(argv[argv.index("--timeout") + 1])
    state = require_enabled(agent_pane_id())
    shared = resolve_shared(state)
    # The shell needs a moment to actually launch what was sent; polling instantly
    # would see the prompt it has not left yet and call the command finished.
    time.sleep(min(WAIT_GRACE_SECONDS, timeout))
    deadline = time.monotonic() + timeout
    running = foreground_command(shared["pane_id"])
    while running and time.monotonic() < deadline:
        time.sleep(WAIT_POLL_SECONDS)
        running = foreground_command(shared["pane_id"])
    if running:
        raise Failure(f"still running `{running}` after {timeout:g}s")
    print(f"{shared['pane_id']} is back at a prompt")


def cmd_send(argv):
    if not argv:
        raise Failure("nothing to send")
    text = " ".join(argv)
    pane_id = agent_pane_id()
    state = require_enabled(pane_id)
    shared = resolve_shared(state)
    busy = foreground_command(shared["pane_id"])
    if busy:
        raise Failure(
            f"{shared['pane_id']} is busy running `{busy}` — not sending. "
            "Wait for it to finish or ask the user."
        )
    herdr("pane", "send-text", shared["pane_id"], text)
    herdr("pane", "send-keys", shared["pane_id"], "enter")
    print(f"sent to {shared['pane_id']}: {text}")


def cmd_status(_argv):
    pane_id = agent_pane_id()
    state = load_state(pane_id)
    if not state:
        print(f"disabled (agent pane {pane_id})")
        return
    print(f"enabled: {pane_id} → {state['shared_pane']}")
    print(f"cursor: {len(state.get('snapshot') or [])} lines")
    print(f"log: {log_path(pane_id)}")


def cmd_disable(_argv):
    pane_id = agent_pane_id()
    clear_state(pane_id)
    print(f"shared-pane collaboration disabled for {pane_id}")


def cmd_cleanup(_argv):
    pane = os.environ.get("HERDR_PANE_ID")
    if pane:
        clear_state(pane)


def cmd_hook(_argv):
    """UserPromptSubmit injection. Never fails loudly; a broken pane must not block a prompt."""
    sys.stdin.read()
    pane_id = os.environ.get("HERDR_PANE_ID")
    if not pane_id:
        return
    state = load_state(pane_id)
    if not state:
        return
    if time.time() - state.get("enabled_at", 0) > STALE_AFTER_SECONDS:
        clear_state(pane_id)
        return
    try:
        shared = resolve_shared(state)
    except Failure:
        clear_state(pane_id)
        emit(
            f"herdr shared pane {state['shared_pane']} is gone; "
            "shared-pane collaboration is now off."
        )
        return
    lines, notice = collect(state, shared)
    if lines:
        emit(render(shared, lines, notice))


def emit(context):
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": context,
                }
            }
        )
    )


COMMANDS = {
    "resolve": cmd_resolve,
    "child": cmd_child,
    "enable": cmd_enable,
    "read": cmd_read,
    "send": cmd_send,
    "wait": cmd_wait,
    "status": cmd_status,
    "disable": cmd_disable,
    "hook": cmd_hook,
    "cleanup": cmd_cleanup,
}


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] not in COMMANDS:
        print(f"usage: herdr-collab.py {{{'|'.join(COMMANDS)}}}", file=sys.stderr)
        return 2
    name, rest = argv[0], argv[1:]
    silent = name in ("hook", "cleanup")
    try:
        COMMANDS[name](rest)
    except Exception as err:  # noqa: BLE001 - hooks must never break the prompt
        if silent:
            return 0
        print(f"herdr-collab: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
