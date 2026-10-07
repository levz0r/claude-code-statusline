#!/usr/bin/env python3
"""Claude Code status line.

Reads the session JSON on stdin and renders a single compact line:

   ~/proj   main +2/-1 ↑1 │ Opus 5 fast │ ███░░░ 41% │ $0.12 · 5m │ 5h 30%

Fields are all optional — anything the running CLI does not send is skipped.
"""
import sys, json, os, re, shutil, subprocess, unicodedata

# ── Kanagawa dragon (dark) / Catppuccin Latte (light) ───────────
def fg(hexcode):
    r, g, b = int(hexcode[1:3], 16), int(hexcode[3:5], 16), int(hexcode[5:7], 16)
    return f"\x1b[38;2;{r};{g};{b}m"


def is_light():
    """Follow the macOS light/dark appearance; anywhere else, assume dark.

    The status line runs on a pipe, so the terminal can't be asked directly.
    STATUSLINE_THEME=light|dark overrides.
    """
    forced = os.environ.get("STATUSLINE_THEME", "").lower()
    if forced in ("light", "dark"):
        return forced == "light"
    try:
        import plistlib
        with open(os.path.expanduser("~/Library/Preferences/.GlobalPreferences.plist"), "rb") as f:
            return plistlib.load(f).get("AppleInterfaceStyle") != "Dark"
    except Exception:
        return False


PALETTES = {
    "dark":  dict(blue="#8ba4b0", mauve="#a292a3", green="#87a987", peach="#b6927b",   # dragon
                  red="#c4746e", yellow="#c4b28a", teal="#8ea4a2", muted="#737c73", text="#c5c9c5"),
    "light": dict(blue="#1e66f5", mauve="#8839ef", green="#40a02b", peach="#fe640b",   # catppuccin latte
                  red="#d20f39", yellow="#df8e1d", teal="#179299", muted="#6c6f85", text="#4c4f69"),
}
P = PALETTES["light" if is_light() else "dark"]

RESET  = "\x1b[0m"
BOLD   = "\x1b[1m"
BLUE   = fg(P["blue"])
MAUVE  = fg(P["mauve"])
GREEN  = fg(P["green"])
PEACH  = fg(P["peach"])
RED    = fg(P["red"])
YELLOW = fg(P["yellow"])
TEAL   = fg(P["teal"])
MUTED  = fg(P["muted"])
FGC    = fg(P["text"])

SEP = f"{MUTED} │ {RESET}"

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def vlen(s):
    """Visible width: escapes are free, wide glyphs cost two columns."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1
               for c in ANSI_RE.sub("", s))


def vtrunc(s, limit):
    """Cut to `limit` visible columns without severing an escape sequence."""
    if vlen(s) <= limit:
        return s
    out, w, i = [], 0, 0
    while i < len(s):
        m = ANSI_RE.match(s, i)
        if m:
            out.append(m.group()); i = m.end(); continue
        cw = 2 if unicodedata.east_asian_width(s[i]) in "WF" else 1
        if w + cw > limit - 1:
            break
        out.append(s[i]); w += cw; i += 1
    return "".join(out) + "…" + RESET


def term_width(default=80):
    """Claude Code exports COLUMNS; every fd here is a pipe, so ioctl is out."""
    try:
        w = shutil.get_terminal_size().columns
        if w > 20:
            return w
    except Exception:
        pass
    return default


def wrap(chunks, width, sep):
    """Greedily pack segments into lines that fit, keeping every segment."""
    seplen, lines, cur, curw = vlen(sep), [], [], 0
    for ch in chunks:
        w = vlen(ch)
        if not cur:
            cur, curw = [ch], w
        elif curw + seplen + w <= width:
            cur.append(ch); curw += seplen + w
        else:
            lines.append(sep.join(cur)); cur, curw = [ch], w
    if cur:
        lines.append(sep.join(cur))
    return [vtrunc(l, width) for l in lines]


def git_info(cwd):
    """branch, dirty-count, ahead, behind — one cheap call, never fatal."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain=v2", "--branch", "--untracked-files=normal"],
            cwd=cwd, capture_output=True, text=True, timeout=1,
        )
        if out.returncode != 0:
            return None
    except Exception:
        return None

    branch, ahead, behind, dirty, untracked = None, 0, 0, 0, 0
    for line in out.stdout.splitlines():
        if line.startswith("# branch.head "):
            branch = line.split(" ", 2)[2]
        elif line.startswith("# branch.ab "):
            parts = line.split()
            ahead, behind = int(parts[2]), abs(int(parts[3]))
        elif line.startswith("?"):
            untracked += 1
        elif line[:1] in ("1", "2", "u"):
            dirty += 1
    if branch in (None, "(detached)"):
        try:
            sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=cwd,
                                 capture_output=True, text=True, timeout=1).stdout.strip()
            branch = f"@{sha}" if sha else "detached"
        except Exception:
            branch = "detached"
    return branch, dirty, untracked, ahead, behind


def short_path(path, home=None):
    home = home or os.path.expanduser("~")
    if path == home:
        return "~"
    if path.startswith(home + os.sep):
        path = "~" + path[len(home):]
    parts = path.split(os.sep)
    if len(parts) > 3:                       # ~/a/b/c/d -> …/c/d
        return os.sep.join(["…"] + parts[-2:])
    return path


def bar(pct, width=6):
    filled = width if pct >= 99.5 else int(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


def human_dur(ms):
    s = int(ms // 1000)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    return f"{s // 3600}h{(s % 3600) // 60:02d}m"


def main():
    try:
        d = json.load(sys.stdin)
    except Exception:
        return  # empty status line beats a traceback

    seg = []

    # ── cwd (+ worktree / added dirs) ───────────────────────────
    ws = d.get("workspace") or {}
    cwd = ws.get("current_dir") or d.get("cwd") or os.getcwd()
    seg.append(f"{BLUE}{BOLD} {short_path(cwd)}{RESET}")

    wt = d.get("worktree") or {}
    if wt.get("name"):
        seg.append(f"{TEAL} {wt['name']}{RESET}")

    extra = len(ws.get("added_dirs") or [])
    if extra:
        seg.append(f"{MUTED}+{extra} dir{'s' if extra > 1 else ''}{RESET}")

    # ── git ─────────────────────────────────────────────────────
    g = git_info(cwd)
    if g:
        branch, dirty, untracked, ahead, behind = g
        bits = [f"{MAUVE} {branch}{RESET}"]
        if dirty:
            bits.append(f"{YELLOW}●{dirty}{RESET}")
        if untracked:
            bits.append(f"{MUTED}?{untracked}{RESET}")
        if ahead:
            bits.append(f"{GREEN}↑{ahead}{RESET}")
        if behind:
            bits.append(f"{RED}↓{behind}{RESET}")
        seg.append(" ".join(bits))

    # ── lines changed this session ──────────────────────────────
    cost = d.get("cost") or {}
    added, removed = cost.get("total_lines_added", 0), cost.get("total_lines_removed", 0)
    if added or removed:
        seg.append(f"{GREEN}+{added}{RESET}{MUTED}/{RESET}{RED}-{removed}{RESET}")

    # ── model / mode ────────────────────────────────────────────
    right = []
    model = (d.get("model") or {}).get("display_name")
    if model:
        m = f"{FGC}{model}{RESET}"
        if d.get("fast_mode"):
            m += f" {YELLOW}{RESET}"
        lvl = (d.get("effort") or {}).get("level")
        if lvl and lvl not in ("medium", "default"):
            m += f" {MUTED}{lvl}{RESET}"
        if (d.get("thinking") or {}).get("enabled") is False:
            m += f" {MUTED}nothink{RESET}"
        right.append(m)

    agent = (d.get("agent") or {}).get("name")
    if agent:
        right.append(f"{TEAL}󰚩 {agent}{RESET}")

    style = (d.get("output_style") or {}).get("name")
    if style and style != "default":
        right.append(f"{MUTED}{style}{RESET}")

    # ── context window ──────────────────────────────────────────
    ctx = d.get("context_window") or {}
    pct = ctx.get("used_percentage")
    if pct is None and ctx.get("context_window_size"):
        used = (ctx.get("total_input_tokens") or 0)
        pct = used / ctx["context_window_size"] * 100
    if pct is not None:
        c = GREEN if pct < 60 else (PEACH if pct < 85 else RED)
        tok = ctx.get("total_input_tokens")
        tokstr = f" {MUTED}{tok / 1000:.0f}k{RESET}" if tok else ""
        right.append(f"{c}{bar(pct)}{RESET} {c}{pct:.0f}%{RESET}{tokstr}")
    elif d.get("exceeds_200k_tokens"):
        right.append(f"{RED}ctx >200k{RESET}")

    # ── cost / duration ─────────────────────────────────────────
    usd, dur = cost.get("total_cost_usd"), cost.get("total_duration_ms")
    if usd is not None:
        c = f"{GREEN} {usd:.2f}{RESET}"
        if dur:
            c += f" {MUTED}· {human_dur(dur)}{RESET}"
        right.append(c)

    # ── rate limits ─────────────────────────────────────────────
    rl = d.get("rate_limits") or {}
    for key, label in (("five_hour", "5h"), ("seven_day", "7d")):
        w = rl.get(key)
        if w and w.get("used_percentage") is not None:
            p = w["used_percentage"]
            c = GREEN if p < 60 else (PEACH if p < 85 else RED)
            right.append(f"{MUTED}{label}{RESET} {c}{p:.0f}%{RESET}")

    # ── PR ──────────────────────────────────────────────────────
    pr = d.get("pr") or {}
    if pr.get("number"):
        right.append(f"{MAUVE} #{pr['number']}{RESET}")

    # ── vim mode ────────────────────────────────────────────────
    vim = (d.get("vim") or {}).get("mode")
    if vim:
        c = PEACH if vim.upper() == "INSERT" else BLUE
        right.append(f"{c}{vim.upper()}{RESET}")

    # One line while it fits; otherwise wrap so nothing falls off a narrow pane.
    width = term_width()
    single = "  ".join(seg) + (SEP + SEP.join(right) if right else "")
    if vlen(single) <= width:
        sys.stdout.write(single)
    else:
        sys.stdout.write("\n".join(wrap(seg + right, width, SEP)))


main()
