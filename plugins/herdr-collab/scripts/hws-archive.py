#!/usr/bin/env python3
"""Archive a herdr space to JSON and close it, or restore an archived space.

Usage:
  hws-archive.py archive [--force] [WORKSPACE_ID]   default: $HERDR_WORKSPACE_ID
  hws-archive.py list                               one line per archive, newest first
  hws-archive.py restore FILE                       rebuild in the current session

Archives live in ~/.config/herdr/archive/. Restored ones move to archive/restored/.
Running shells and scrollback are not kept; agent panes resume their conversations.
"""
import datetime
import json
import os
import re
import shlex
import shutil
import socket
import sys

SOCKET = os.environ.get("HERDR_SOCKET_PATH") or os.path.expanduser(
    "~/.config/herdr/herdr.sock"
)
ARCHIVE_DIR = os.path.expanduser("~/.config/herdr/archive")
RESTORED_DIR = os.path.join(ARCHIVE_DIR, "restored")
FORMAT_VERSION = 1

# From herdr's session-state docs (native agent session restore table).
RESUME = {
    "claude": "claude --resume {}",
    "codex": "codex resume {}",
    "pi": "pi --session {}",
    "omp": "omp --resume={}",
    "agy": "agy --conversation {}",
    "antigravity-cli": "agy --conversation {}",
    "cursor": "cursor-agent --resume {}",
    "grok": "grok --resume {}",
    "copilot": "copilot --resume={}",
    "devin": "devin --resume {}",
    "droid": "droid --resume {}",
    "kimi": "kimi --session {}",
    "qodercli": "qodercli --resume {}",
    "qwen": "qwen --resume {}",
    "opencode": "opencode --session {}",
    "kilo": "kilo --session {}",
    "hermes": "hermes --resume {}",
    "mastracode": "mastracode --thread {}",
}


def call(method, params):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(SOCKET)
    s.sendall((json.dumps({"id": "hws-archive", "method": method, "params": params}) + "\n").encode())
    s.settimeout(10)
    buf = b""
    while b"\n" not in buf:
        chunk = s.recv(65536)
        if not chunk:
            break
        buf += chunk
    reply = json.loads(buf.split(b"\n")[0])
    if "error" in reply:
        raise SystemExit("hws-archive: %s: %s" % (method, reply["error"].get("message", reply["error"])))
    return reply["result"]


def bbox(rects):
    x0 = min(r["x"] for r in rects)
    y0 = min(r["y"] for r in rects)
    x1 = max(r["x"] + r["width"] for r in rects)
    y1 = max(r["y"] + r["height"] for r in rects)
    return (x0, y0, x1 - x0, y1 - y0)


def rect_key(r):
    return (r["x"], r["y"], r["width"], r["height"])


def build_tree(panes, splits):
    """Rebuild the split tree from the flat rects in a live layout."""
    if len(panes) == 1:
        return {"pane": panes[0]["pane_id"]}
    region = bbox([p["rect"] for p in panes])
    split = next((s for s in splits if rect_key(s["rect"]) == region), None)
    if split is None:
        raise SystemExit("hws-archive: cannot reconstruct layout (zoomed tab?)")
    horizontal = split["direction"] == "right"
    pos, size = ("x", "width") if horizontal else ("y", "height")
    # The boundary is the pane edge that cleanly separates the panes, nearest the ratio.
    target = split["rect"][pos] + split["rect"][size] * split["ratio"]
    edges = sorted({p["rect"][pos] for p in panes if p["rect"][pos] > split["rect"][pos]})
    clean = [
        e for e in edges
        if all(p["rect"][pos] >= e or p["rect"][pos] + p["rect"][size] <= e for p in panes)
    ]
    if not clean:
        raise SystemExit("hws-archive: cannot split layout region %s" % (region,))
    edge = min(clean, key=lambda e: abs(e - target))
    first = [p for p in panes if p["rect"][pos] < edge]
    second = [p for p in panes if p["rect"][pos] >= edge]
    return {
        "direction": split["direction"],
        "ratio": split["ratio"],
        "first": build_tree(first, splits),
        "second": build_tree(second, splits),
    }


def map_leaves(node, fn):
    if "pane" in node:
        return {"pane": fn(node["pane"])}
    return dict(node, first=map_leaves(node["first"], fn), second=map_leaves(node["second"], fn))


def pane_record(p):
    rec = {"cwd": p.get("foreground_cwd") or p.get("cwd") or os.path.expanduser("~")}
    if p.get("label"):
        rec["label"] = p["label"]
    sess = p.get("agent_session")
    if sess and sess.get("value"):
        rec["agent"] = {"agent": sess["agent"], "kind": sess.get("kind"), "value": sess["value"]}
    return rec


def slug(text):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-")[:40] or "space"


def archive(args):
    force = "--force" in args
    rest = [a for a in args if a != "--force"]
    ws_id = rest[0] if rest else os.environ.get("HERDR_WORKSPACE_ID")
    if not ws_id:
        raise SystemExit("hws-archive: not in a herdr space and no workspace id given")

    snap = call("session.snapshot", {})["snapshot"]
    ws = next((w for w in snap["workspaces"] if w["workspace_id"] == ws_id), None)
    if ws is None:
        raise SystemExit("hws-archive: no workspace %s" % ws_id)
    panes = {p["pane_id"]: p for p in snap["panes"] if p["workspace_id"] == ws_id}

    busy = [p["pane_id"] for p in panes.values() if p.get("agent_status") == "working"]
    if busy and not force:
        raise SystemExit("hws-archive: agents still working in %s; rerun with --force" % ", ".join(busy))

    tabs = []
    for tab in (t for t in snap["tabs"] if t["workspace_id"] == ws_id):
        layout = next((l for l in snap["layouts"] if l["tab_id"] == tab["tab_id"]), None)
        if layout is None:
            raise SystemExit("hws-archive: no layout for tab %s" % tab["tab_id"])
        tree = build_tree(layout["panes"], layout["splits"])
        tabs.append({
            "label": tab["label"],
            "active": tab["tab_id"] == ws["active_tab_id"],
            "layout": map_leaves(tree, lambda pid: pane_record(panes[pid])),
        })

    now = datetime.datetime.now().astimezone()
    record = {
        "version": FORMAT_VERSION,
        "label": ws["label"],
        "archived_at": now.isoformat(timespec="seconds"),
        "source_workspace_id": ws_id,
        "tabs": tabs,
    }
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    path = os.path.join(ARCHIVE_DIR, "%s_%s_%s.json" % (now.strftime("%Y-%m-%dT%H%M"), slug(ws["label"]), ws_id))
    with open(path, "w") as f:
        json.dump(record, f, indent=2)
    try:
        call("workspace.close", {"workspace_id": ws_id})
    except SystemExit as e:
        raise SystemExit("%s\nhws-archive: space left open; archive already saved at %s" % (e, path))
    print("archived %s → %s" % (ws["label"], path))


def leaves(node):
    if "pane" in node:
        return [node["pane"]]
    return leaves(node["first"]) + leaves(node["second"])


def setup_pane(pane_id, rec):
    if rec.get("label"):
        call("pane.rename", {"pane_id": pane_id, "label": rec["label"]})
    agent = rec.get("agent")
    if not agent:
        return
    template = RESUME.get(agent["agent"])
    if template is None:
        print("hws-archive: no resume command for %s; left a shell in %s" % (agent["agent"], rec["cwd"]), file=sys.stderr)
        return
    call("pane.send_input", {"pane_id": pane_id, "text": template.format(shlex.quote(agent["value"])), "keys": ["Enter"]})


def realize(node, pane_id):
    """Turn pane_id into the given subtree."""
    if "pane" in node:
        setup_pane(pane_id, node["pane"])
        return
    second_cwd = leaves(node["second"])[0]["cwd"]
    new = call("pane.split", {
        "target_pane_id": pane_id,
        "direction": node["direction"],
        "ratio": node["ratio"],
        "cwd": second_cwd,
        "focus": False,
    })["pane"]["pane_id"]
    realize(node["first"], pane_id)
    realize(node["second"], new)


def restore(args):
    if len(args) != 1:
        raise SystemExit("usage: hws-archive.py restore FILE")
    path = args[0]
    with open(path) as f:
        record = json.load(f)
    if record.get("version") != FORMAT_VERSION:
        raise SystemExit("hws-archive: unsupported archive version %r" % record.get("version"))

    ws_id = None
    active_tab = None
    for i, tab in enumerate(record["tabs"]):
        cwd = leaves(tab["layout"])[0]["cwd"]
        if i == 0:
            res = call("workspace.create", {"cwd": cwd, "label": record["label"], "focus": False})
            ws_id = res["workspace"]["workspace_id"]
            tab_id = res["tab"]["tab_id"]
            if not tab["label"].isdigit():
                call("tab.rename", {"tab_id": tab_id, "label": tab["label"]})
        else:
            res = call("tab.create", {"workspace_id": ws_id, "cwd": cwd, "focus": False,
                                    "label": None if tab["label"].isdigit() else tab["label"]})
            tab_id = res["tab"]["tab_id"]
        realize(tab["layout"], res["root_pane"]["pane_id"])
        if tab.get("active"):
            active_tab = tab_id

    call("workspace.focus", {"workspace_id": ws_id})
    if active_tab:
        call("tab.focus", {"tab_id": active_tab})

    os.makedirs(RESTORED_DIR, exist_ok=True)
    shutil.move(path, os.path.join(RESTORED_DIR, os.path.basename(path)))
    print("restored %s as %s" % (record["label"], ws_id))


def list_archives():
    if not os.path.isdir(ARCHIVE_DIR):
        return
    names = sorted((n for n in os.listdir(ARCHIVE_DIR) if n.endswith(".json")), reverse=True)
    for name in names:
        path = os.path.join(ARCHIVE_DIR, name)
        try:
            with open(path) as f:
                rec = json.load(f)
        except (OSError, ValueError) as e:
            print("hws-archive: skipping %s: %s" % (path, e), file=sys.stderr)
            continue
        all_panes = [p for t in rec["tabs"] for p in leaves(t["layout"])]
        agents = sorted({p["agent"]["agent"] for p in all_panes if p.get("agent")})
        print("\t".join([
            path,
            rec["archived_at"][:16].replace("T", " "),
            rec["label"],
            "%d tabs" % len(rec["tabs"]),
            ",".join(agents) or "-",
            all_panes[0]["cwd"].replace(os.path.expanduser("~"), "~"),
        ]))


COMMANDS = {"archive": archive, "restore": restore, "list": lambda _: list_archives()}

if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
    raise SystemExit(__doc__)
COMMANDS[sys.argv[1]](sys.argv[2:])
