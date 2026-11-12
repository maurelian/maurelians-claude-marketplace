#!/usr/bin/env python3
"""Write demo.cast: a scripted herdr-collab session, rendered to demo.gif with agg.

    python3 make-demo.py && agg --font-size 16 --theme monokai demo.cast demo.gif
"""

import json
from pathlib import Path

W, H = 100, 24
SPLIT = 55  # column of the divider between the two panes
TOP, BOTTOM = 3, H - 1  # first and last content rows

RESET = "\x1b[0m"
DIM = "\x1b[38;5;244m"
BORDER = "\x1b[38;5;240m"
ACCENT = "\x1b[38;5;214m"
CLAUDE = "\x1b[38;5;209m"
GREEN = "\x1b[38;5;114m"
RED = "\x1b[38;5;203m"
CYAN = "\x1b[38;5;117m"
BOLD = "\x1b[1m"
INV_RED = "\x1b[48;5;203;38;5;16m"
INV_GREEN = "\x1b[48;5;114;38;5;16m"


class Cast:
    def __init__(self):
        self.t = 0.0
        self.events = []
        self.rows = {"claude": TOP, "shell": TOP}

    def out(self, s, delay=0.0):
        self.t += delay
        self.events.append([round(self.t, 3), "o", s])

    def pause(self, s):
        self.t += s

    def at(self, row, col, s, delay=0.0):
        self.out(f"\x1b[{row};{col}H{s}{RESET}", delay)

    def col(self, pane):
        return 3 if pane == "claude" else SPLIT + 3

    def line(self, pane, s="", delay=0.05):
        self.at(self.rows[pane], self.col(pane), s, delay)
        self.rows[pane] += 1

    def type(self, pane, prefix, text, cps=14, suffix_color=""):
        """Type text after a prefix on the pane's next line, then move down."""
        row, col = self.rows[pane], self.col(pane)
        self.at(row, col, prefix)
        col += visible_len(prefix)
        for ch in text:
            self.at(row, col, suffix_color + ch, 1 / cps)
            col += 1
        self.pause(0.35)
        self.rows[pane] += 1

    def title(self, pane, label, color):
        col = 2 if pane == "claude" else SPLIT + 1
        self.at(2, col + 1, f"{color} {label} ")

    def save(self, path):
        header = {"version": 2, "width": W, "height": H,
                  "title": "herdr-collab", "env": {"TERM": "xterm-256color"}}
        lines = [json.dumps(header)] + [json.dumps(e, ensure_ascii=False) for e in self.events]
        Path(path).write_text("\n".join(lines) + "\n")


def visible_len(s):
    n, esc = 0, False
    for ch in s:
        if ch == "\x1b":
            esc = True
        elif esc and ch == "m":
            esc = False
        elif not esc:
            n += 1
    return n


def frame(c):
    c.out("\x1b[2J\x1b[?25l")
    c.at(1, 1, f"{ACCENT}{BOLD} herdr {RESET}{DIM} demo  {RESET}{BORDER}│{RESET}{DIM} 1 claude  2 shell")
    left_w, right_w = SPLIT - 2, W - SPLIT - 1
    c.at(2, 1, BORDER + "╭" + "─" * left_w + "╮" + "╭" + "─" * (right_w - 1) + "╮")
    for r in range(TOP, BOTTOM):
        c.at(r, 1, BORDER + "│")
        c.at(r, SPLIT, BORDER + "││")
        c.at(r, W, BORDER + "│")
    c.at(BOTTOM, 1, BORDER + "╰" + "─" * left_w + "╯" + "╰" + "─" * (right_w - 1) + "╯")
    c.title("claude", "claude", DIM)
    c.title("shell", "~/proj", DIM)
    c.at(H, 2, f"{DIM}ctrl+f prefix · the right pane is yours; Claude sees what it prints")


def prompt(c, cmd, cps=14):
    c.type("shell", f"{CYAN}~/proj{RESET} $ ", cmd, cps=cps)


def run_tests(c, failing):
    c.line("shell", f"{INV_GREEN} PASS {RESET} src/api.test.ts", 0.6)
    if failing:
        c.line("shell", f"{INV_RED} FAIL {RESET} src/date.test.ts", 0.3)
        c.line("shell", f"  {RED}✕{RESET} parses ISO dates")
        c.line("shell", f"    Expected: {GREEN}\"2026-11-12\"")
        c.line("shell", f"    Received: {RED}\"2026-11-11\"")
        c.line("shell", f"Tests: {RED}1 failed{RESET}, 41 passed", 0.2)
    else:
        c.line("shell", f"{INV_GREEN} PASS {RESET} src/date.test.ts", 0.3)
        c.line("shell", f"Tests: {GREEN}42 passed", 0.2)
    c.line("shell", f"{CYAN}~/proj{RESET} $ ", 0.2)
    c.rows["shell"] -= 1  # leave the cursor on the idle prompt


def claude(c, *lines, delay=0.06):
    for i, s in enumerate(lines):
        c.line("claude", (f"{CLAUDE}●{RESET} " if i == 0 else "  ") + s, delay)


def main():
    c = Cast()
    frame(c)
    c.pause(0.8)

    c.type("claude", f"{DIM}>{RESET} ", "watch my pane")
    c.pause(0.6)
    claude(c, f"{BOLD}Skill{RESET}(herdr-collab)")
    c.pause(0.9)
    claude(c, "Sharing pane w1:p2 (~/proj). New output",
           "there reaches me every turn, and I can",
           "type into it.")
    c.title("shell", f"~/proj · {ACCENT}shared{RESET}", "")
    c.line("claude")
    c.pause(1.4)

    prompt(c, "npm test")
    run_tests(c, failing=True)
    c.pause(1.6)

    c.type("claude", f"{DIM}>{RESET} ", "why did that fail?")
    c.line("claude", f"  {DIM}⎿ shared pane w1:p2 · 7 new lines")
    c.line("claude")
    c.pause(1.4)
    claude(c, f"parseDate builds a {BOLD}local{RESET} Date, but the",
           "test runs in UTC. Fixing src/date.ts:14.")
    c.line("claude")
    c.pause(0.9)
    claude(c, f"{BOLD}Update{RESET}(src/date.ts)",
           f"{DIM}⎿{RESET} {RED}- new Date(y, m - 1, d)",
           f"  {GREEN}+ new Date(Date.UTC(y, m - 1, d))")
    c.line("claude")
    c.pause(1.0)
    claude(c, "Re-running it in your pane.",)
    claude(c, f"{BOLD}Bash{RESET}(herdr-collab.py send npm test)")
    c.pause(0.5)

    prompt(c, "npm test", cps=60)
    run_tests(c, failing=False)
    c.pause(1.0)

    claude(c, f"{GREEN}42 passed.{RESET} Fixed.")
    c.pause(4.0)
    c.out("", 0)

    c.save(Path(__file__).with_name("demo.cast"))


if __name__ == "__main__":
    main()
