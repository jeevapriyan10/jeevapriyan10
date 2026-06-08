#!/usr/bin/env python3
"""
generate_svg.py — Andrew6rant-style neofetch SVG for jeevapriyan10
- Image on left, stats on right
- Keys LEFT-aligned, values RIGHT-aligned, dots fill the middle
- Fixed monospace character grid — every line same total width
- Long values wrap to next line with dot-prefix on continuation
"""

import os, base64, requests
from datetime import date, datetime, timezone
from pathlib import Path

# ── CONFIG ────────────────────────────────────────────────────────────────────
GITHUB_USERNAME  = "jeevapriyan10"
GITHUB_JOIN_DATE = date(2021, 7, 1)   # approximate — will be fetched live
BIRTHDAY         = date(2007, 1, 19)
TOKEN            = os.environ.get("GITHUB_TOKEN", "")
HEADERS          = {"Authorization": f"bearer {TOKEN}"} if TOKEN else {}
IMAGE_PATH       = Path("assets/me.jpg")
OUTPUT_PATH      = Path("dark_mode.svg")

# ── FONT / CHAR GRID ──────────────────────────────────────────────────────────
# Fira Code 13px → ~7.82px per char (measured)
CHAR_W   = 7.82
FS       = 13
LINE_H   = 21
FONT     = "Fira Code, Cascadia Code, Consolas, monospace"

# Total characters per line in the text block (key + dots + value)
LINE_W   = 62   # chars — matches Andrew's ~62 char wide block

# ── IMAGE ─────────────────────────────────────────────────────────────────────
IMG_W    = 310   # px
IMG_PAD  = 22   # gap between image and text block
SVG_PAD  = 18   # outer padding

# ── COLORS (exact Andrew6rant palette) ────────────────────────────────────────
BG       = "#0d1117"
HEADER_C = "#e05d44"   # orange-red  — "username@dev"
DASH_C   = "#21262d"   # dark grey   — divider dashes & header dashes
LABEL_C  = "#f0883e"   # amber       — keys & section names  (Andrew uses orange)
DOT_C    = "#3d444d"   # mid-grey    — dot fill
VALUE_C  = "#e6edf3"   # near-white  — values
GREEN_C  = "#3fb950"   # green       — LOC added
RED_C    = "#f85149"   # red         — LOC deleted
DIM_C    = "#8b949e"   # dim grey    — bullet "."

DASH     = "─"
DOT      = "."

# ── HELPERS ───────────────────────────────────────────────────────────────────
def esc(s):
    return (s.replace("&","&amp;")
             .replace("<","&lt;")
             .replace(">","&gt;")
             .replace('"',"&quot;"))

def rest(ep):
    r = requests.get(f"https://api.github.com/{ep}",
                     headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()

def gql(q):
    r = requests.post("https://api.github.com/graphql",
                      json={"query": q}, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()

def account_uptime(join_iso: str) -> str:
    """Return 'X years Y months Z days' since GitHub account creation."""
    joined = datetime.fromisoformat(join_iso.replace("Z","+00:00")).date()
    today  = date.today()
    years  = today.year  - joined.year
    months = today.month - joined.month
    days   = today.day   - joined.day
    if days   < 0: months -= 1; days   += 30
    if months < 0: years  -= 1; months += 12
    return f"{years}y {months}m {days}d"

def fmt(n): return f"{n:,}"

# ── GITHUB DATA ───────────────────────────────────────────────────────────────
def fetch_stats() -> dict:
    print("Fetching GitHub stats...")

    # User info (public repos, followers, join date)
    user        = rest(f"users/{GITHUB_USERNAME}")
    repos_count = user.get("public_repos", 0)
    followers   = user.get("followers", 0)
    join_iso    = user.get("created_at", "2021-07-01T00:00:00Z")
    uptime_str  = account_uptime(join_iso)

    stars = commits = contributions = loc_add = loc_del = 0

    # Stars
    all_repos, page = [], 1
    while True:
        batch = rest(f"users/{GITHUB_USERNAME}/repos?per_page=100&page={page}")
        if not batch: break
        all_repos.extend(batch); page += 1
    for r in all_repos:
        stars += r.get("stargazers_count", 0)

    # Commits + contributions via GraphQL
    try:
        q = f"""{{
          user(login: "{GITHUB_USERNAME}") {{
            contributionsCollection {{
              totalCommitContributions
              restrictedContributionsCount
              totalPullRequestContributions
              totalIssueContributions
              totalRepositoryContributions
            }}
            createdAt
          }}
        }}"""
        data = gql(q)["data"]["user"]
        cc   = data["contributionsCollection"]
        commits       = (cc.get("totalCommitContributions", 0)
                         + cc.get("restrictedContributionsCount", 0))
        contributions = (commits
                         + cc.get("totalPullRequestContributions", 0)
                         + cc.get("totalIssueContributions", 0)
                         + cc.get("totalRepositoryContributions", 0))
    except Exception as e:
        print(f"  warn GraphQL: {e}")

    # Lines of code
    print("  Counting lines of code...")
    for repo in all_repos:
        try:
            s = rest(f"repos/{GITHUB_USERNAME}/{repo['name']}/stats/contributors")
            if not isinstance(s, list): continue
            for c in s:
                if c.get("author",{}).get("login","").lower() == GITHUB_USERNAME.lower():
                    for w in c.get("weeks",[]):
                        loc_add += w.get("a", 0)
                        loc_del += w.get("d", 0)
        except: pass

    return dict(
        uptime       = uptime_str,
        repos        = repos_count,
        followers    = followers,
        stars        = stars,
        commits      = commits,
        contributions= contributions,
        loc_add      = loc_add,
        loc_del      = loc_del,
        loc_net      = loc_add - loc_del,
    )

# ── LINE BUILDER ──────────────────────────────────────────────────────────────
# A "rendered line" is a list of (text, color) segments.
# We build logical lines first, then wrap long ones.

def build_kv_line(key: str, value: str, line_w: int = LINE_W) -> list[list]:
    """
    Build one or more rendered lines for a key-value pair.
    Format: ". KEY: ........ VALUE"
    Key is left-aligned, value is right-aligned, dots fill the gap.
    If value is too long to fit on one line, it wraps with dot-prefix.
    """
    prefix   = ". "
    key_part = f"{key}: "
    # available chars for dots + value on first line
    # total = prefix + key_part + dots + " " + value
    # we right-align value so: dots fill (line_w - len(prefix) - len(key_part) - 1 - len(value))
    avail    = line_w - len(prefix) - len(key_part) - 1  # 1 for space before value

    lines_out = []

    if len(value) <= avail:
        dot_count = avail - len(value)
        dots      = DOT * dot_count
        lines_out.append([
            (prefix,    DIM_C),
            (key_part,  LABEL_C),
            (dots,      DOT_C),
            (" ",       DOT_C),
            (value,     VALUE_C),
        ])
    else:
        # Split value into chunks that fit
        # First line: as much of value as possible
        # Continuation lines: dot prefix fills left, value right-aligned
        dot_count_first = 3   # minimum dots on first line
        first_val_len   = avail - dot_count_first
        first_val       = value[:first_val_len].rstrip()
        rest_val        = value[first_val_len:].strip()

        dots_first = DOT * dot_count_first
        lines_out.append([
            (prefix,       DIM_C),
            (key_part,     LABEL_C),
            (dots_first,   DOT_C),
            (" ",          DOT_C),
            (first_val,    VALUE_C),
        ])

        # Continuation lines
        cont_avail = line_w - 1  # 1 space on left
        while rest_val:
            chunk    = rest_val[:cont_avail].rstrip()
            rest_val = rest_val[len(chunk):].strip()
            dot_c    = DOT * (cont_avail - len(chunk))
            lines_out.append([
                (dot_c,   DOT_C),
                (" ",     DOT_C),
                (chunk,   VALUE_C),
            ])

    return lines_out

def build_kv_multi(key: str, val_segs: list, line_w: int = LINE_W) -> list[list]:
    """KV line where value is a list of (text, color) segments (e.g. LOC line)."""
    prefix    = ". "
    key_part  = f"{key}: "
    val_text  = "".join(t for t, _ in val_segs)
    avail     = line_w - len(prefix) - len(key_part) - 1
    dot_count = max(3, avail - len(val_text))
    dots      = DOT * dot_count
    row = [
        (prefix,   DIM_C),
        (key_part, LABEL_C),
        (dots,     DOT_C),
        (" ",      DOT_C),
    ]
    row.extend(val_segs)
    return [row]

def build_section(label: str, line_w: int = LINE_W) -> list[list]:
    dash_count = line_w - len(label) - 3
    return [[
        ("- ",              DIM_C),
        (label,             LABEL_C),
        (f" {DASH*dash_count}", DASH_C),
    ]]

def build_header(username: str, line_w: int = LINE_W) -> list[list]:
    tag       = f"{username}@dev"
    dash_count= line_w - len(tag) - 1
    return [[
        (tag,                HEADER_C),
        (f" {DASH*dash_count}", DASH_C),
    ]]

def blank_line() -> list[list]:
    return [[("", VALUE_C)]]

# ── SVG RENDERER ──────────────────────────────────────────────────────────────
def render_seg_line(segs, x, y) -> str:
    inner = "".join(f'<tspan fill="{c}">{esc(t)}</tspan>' for t, c in segs if t)
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" '
            f'font-size="{FS}" xml:space="preserve">{inner}</text>')

def encode_image(path: Path) -> str:
    if not path.exists():
        print(f"  warn: {path} not found"); return ""
    data = base64.b64encode(path.read_bytes()).decode()
    ext  = path.suffix.lower().lstrip(".")
    mime = "jpeg" if ext in ("jpg","jpeg") else ext
    return f"data:image/{mime};base64,{data}"

# ── MAIN BUILD ────────────────────────────────────────────────────────────────
def build_svg(stats: dict) -> str:
    img_data = encode_image(IMAGE_PATH)

    # ── Compose all rows ─────────────────────────────────────────────────────
    rows = []   # each item: list of (text, color) segments

    def add(lines): rows.extend(lines)

    add(build_header(GITHUB_USERNAME))
    add(blank_line())
    add(build_kv_line("OS",     "Windows 11, Android 16"))
    add(build_kv_line("Uptime", stats["uptime"]))
    add(build_kv_line("IDE",    "VS Code, Notepad, Pen & Paper"))
    add(blank_line())
    add(build_section("Languages"))
    add(build_kv_line("Languages.Programming", "C, C++, Python, Java, JS, TS",              line_w=LINE_W))
    add(build_kv_line("Languages.Computer",    "HTML, CSS, JSON, MD, BASH, PS, GIT, SQL",   line_w=LINE_W))
    add(build_kv_line("Languages.Real",        "English, Tamil",                            line_w=LINE_W))
    add(blank_line())
    add(build_section("Contact"))
    add(build_kv_line("Email",     "jeeva.mail10@gmail.com"))
    add(build_kv_line("LinkedIn",  "jeevapriyan11"))
    add(build_kv_line("Twitter",   "jeevapriyan10"))
    add(build_kv_line("Telegram",  "jeevapriyan10"))
    add(build_kv_line("Instagram", "ft.jeevz_"))
    add(blank_line())
    add(build_section("GitHub Stats"))
    add(build_kv_line("Repos",         fmt(stats["repos"])))
    add(build_kv_line("Commits",       fmt(stats["commits"])))
    add(build_kv_line("Contributions", fmt(stats["contributions"])))
    add(build_kv_multi("Lines of Code", [
        (fmt(stats["loc_net"]),        VALUE_C),
        ("  (",                        VALUE_C),
        (f"+{fmt(stats['loc_add'])}",  GREEN_C),
        (", ",                         VALUE_C),
        (f"-{fmt(stats['loc_del'])}",  RED_C),
        (")",                          VALUE_C),
    ]))

    # ── Dimensions ───────────────────────────────────────────────────────────
    n          = len(rows)
    txt_px_w   = int(LINE_W * CHAR_W) + 4
    txt_px_h   = n * LINE_H + SVG_PAD

    img_h      = txt_px_h - SVG_PAD        # image height matches text block
    SVG_W      = SVG_PAD + IMG_W + IMG_PAD + txt_px_w + SVG_PAD
    SVG_H      = txt_px_h + SVG_PAD * 2

    img_x      = SVG_PAD
    img_y      = SVG_PAD
    text_x     = SVG_PAD + IMG_W + IMG_PAD
    start_y    = SVG_PAD + LINE_H           # first baseline

    # ── SVG elements ─────────────────────────────────────────────────────────
    els = []
    els.append(f'<rect width="{SVG_W}" height="{SVG_H}" fill="{BG}" rx="8"/>')

    if img_data:
        els.append(
            f'<defs><clipPath id="ic">'
            f'<rect x="{img_x}" y="{img_y}" '
            f'width="{IMG_W}" height="{img_h}" rx="6"/>'
            f'</clipPath></defs>'
        )
        els.append(
            f'<image href="{img_data}" x="{img_x}" y="{img_y}" '
            f'width="{IMG_W}" height="{img_h}" '
            f'preserveAspectRatio="xMidYMid slice" clip-path="url(#ic)"/>'
        )

    for i, row in enumerate(rows):
        y = start_y + i * LINE_H
        if not any(t for t, _ in row): continue
        els.append(render_seg_line(row, text_x, y))

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{SVG_W}" height="{SVG_H}" '
        f'viewBox="0 0 {SVG_W} {SVG_H}">\n'
        + "\n".join(f"  {e}" for e in els)
        + "\n</svg>"
    )

# ── ENTRY POINT ───────────────────────────────────────────────────────────────
def main():
    stats = fetch_stats()
    print(f"  uptime={stats['uptime']}  repos={stats['repos']}  "
          f"commits={stats['commits']}  contributions={stats['contributions']}  "
          f"loc_net={stats['loc_net']:,}")
    svg = build_svg(stats)
    OUTPUT_PATH.write_text(svg, encoding="utf-8")
    print(f"Written → {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
