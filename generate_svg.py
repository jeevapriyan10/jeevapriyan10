#!/usr/bin/env python3
"""
generate_svg.py — Andrew6rant-style neofetch SVG generator for jeevapriyan10
Fixed-width monospace block: dots fill the gap, values right-aligned.
"""

import os, base64, requests
from datetime import date
from pathlib import Path

# ── CONFIG ────────────────────────────────────────────────────────────────────
GITHUB_USERNAME = "jeevapriyan10"
BIRTHDAY        = date(2007, 1, 19)
TOKEN           = os.environ.get("GITHUB_TOKEN", "")
HEADERS         = {"Authorization": f"token {TOKEN}"} if TOKEN else {}
IMAGE_PATH      = Path("assets/me.jpg")
OUTPUT_PATH     = Path("dark_mode.svg")

# ── FONT / LAYOUT ─────────────────────────────────────────────────────────────
# Fira Code at 13px → each char ≈ 7.8px wide (monospace)
CHAR_W   = 7.8
FS       = 13
FONT     = "Fira Code, Cascadia Code, Consolas, monospace"
LINE_H   = 21

# Fixed total line width in characters (matches Andrew's ~80-char lines)
LINE_CHARS = 68          # chars from "." prefix to end of value
DOT_CHAR   = "."         # dot fill character (Andrew uses ".")
DASH_CHAR  = "─"

# Image block
IMG_W    = 300
IMG_H    = None          # calculated from line count
IMG_PAD  = 20            # padding around image

# Text block starts after image
TEXT_X   = IMG_W + IMG_PAD * 2 + 10
SVG_PAD  = 20

# Colors
BG       = "#0d1117"
HEADER_C = "#f78166"   # orange — "jeevapriyan10@dev"
DASH_C   = "#21262d"   # dark   — divider dashes
LABEL_C  = "#58a6ff"   # blue   — keys, section names
DOT_C    = "#3d444d"   # grey   — dot fill
VALUE_C  = "#e6edf3"   # white  — values
GREEN_C  = "#3fb950"   # green  — LOC added
RED_C    = "#f85149"   # red    — LOC deleted
DIM_C    = "#8b949e"   # dim    — bullet dots

# ── GITHUB API ────────────────────────────────────────────────────────────────
def rest(ep):
    r = requests.get(f"https://api.github.com/{ep}", headers=HEADERS, timeout=30)
    r.raise_for_status(); return r.json()

def gql(q):
    r = requests.post("https://api.github.com/graphql",
                      json={"query": q}, headers=HEADERS, timeout=30)
    r.raise_for_status(); return r.json()

def uptime():
    t = date.today()
    y = t.year - BIRTHDAY.year
    m = t.month - BIRTHDAY.month
    if m < 0: y -= 1; m += 12
    return f"{y} years, {m} months"

def fmt(n): return f"{n:,}"

def fetch_stats():
    print("Fetching stats...")
    user        = rest(f"users/{GITHUB_USERNAME}")
    repos_count = user.get("public_repos", 0)
    followers   = user.get("followers", 0)
    stars = commits = loc_add = loc_del = 0

    all_repos, page = [], 1
    while True:
        batch = rest(f"users/{GITHUB_USERNAME}/repos?per_page=100&page={page}")
        if not batch: break
        all_repos.extend(batch); page += 1
    for r in all_repos:
        stars += r.get("stargazers_count", 0)

    try:
        q = f"""{{ user(login:"{GITHUB_USERNAME}") {{
            contributionsCollection {{
              totalCommitContributions restrictedContributionsCount }} }} }}"""
        cc = gql(q)["data"]["user"]["contributionsCollection"]
        commits = cc.get("totalCommitContributions",0) + cc.get("restrictedContributionsCount",0)
    except Exception as e:
        print(f"  warn commits: {e}")

    print("  Counting lines of code...")
    for repo in all_repos:
        try:
            stats = rest(f"repos/{GITHUB_USERNAME}/{repo['name']}/stats/contributors")
            if not isinstance(stats, list): continue
            for c in stats:
                if c.get("author",{}).get("login","").lower() == GITHUB_USERNAME.lower():
                    for w in c.get("weeks",[]):
                        loc_add += w.get("a",0); loc_del += w.get("d",0)
        except: pass

    return dict(repos=repos_count, followers=followers, stars=stars,
                commits=commits, loc_add=loc_add, loc_del=loc_del,
                loc_net=loc_add-loc_del)

# ── LINE BUILDER ──────────────────────────────────────────────────────────────
# Each line = list of (text, color) segments
# We use a fixed-width approach:
#   ". KEY: " + dots + " VALUE"
#   Total visible chars = LINE_CHARS

def esc(s):
    return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def make_kv(key, value, prefix=". ", key_width=22):
    """
    Build a KV line with dot-fill so total = LINE_CHARS.
    Returns list of (text, color) segments.
    key_width: fixed chars reserved for key (right-pad with dots).
    """
    key_str   = f"{prefix}{key}: "
    # pad key to key_width with dots
    dot_count = max(2, key_width - len(key_str))
    dot_str   = DOT_CHAR * dot_count
    # right-pad value space: total line should be LINE_CHARS
    # value just appended after dots + space
    return [
        (prefix,    DIM_C),
        (f"{key}: ", LABEL_C),
        (dot_str,   DOT_C),
        (" ",        DOT_C),
        (value,     VALUE_C),
    ]

def make_kv_multi(key, val_segs, prefix=". ", key_width=22):
    key_str   = f"{prefix}{key}: "
    dot_count = max(2, key_width - len(key_str))
    dot_str   = DOT_CHAR * dot_count
    segs = [
        (prefix,    DIM_C),
        (f"{key}: ", LABEL_C),
        (dot_str,   DOT_C),
        (" ",        DOT_C),
    ]
    segs.extend(val_segs)
    return segs

def make_section(label, total=LINE_CHARS):
    dash_count = total - len(label) - 4
    dash_str   = DASH_CHAR * max(2, dash_count)
    return [
        ("- ",      DIM_C),
        (label,     LABEL_C),
        (f" {dash_str}", DASH_C),
    ]

def make_header(username, total=LINE_CHARS):
    suffix     = DASH_CHAR * (total - len(username) - 5)
    return [
        (f"{username}@dev ", HEADER_C),
        (suffix,             DASH_C),
    ]

# ── SVG RENDERER ──────────────────────────────────────────────────────────────
def render_line_segs(segs, x, y):
    """Render a list of (text, color) at position x, y using tspan."""
    inner = "".join(
        f'<tspan fill="{c}">{esc(t)}</tspan>'
        for t, c in segs if t
    )
    return (
        f'<text x="{x}" y="{y}" '
        f'font-family="{FONT}" font-size="{FS}" '
        f'xml:space="preserve">{inner}</text>'
    )

def build_svg(stats):
    img_data = ""
    if IMAGE_PATH.exists():
        data     = base64.b64encode(IMAGE_PATH.read_bytes()).decode()
        ext      = IMAGE_PATH.suffix.lower().lstrip(".")
        mime     = "jpeg" if ext in ("jpg","jpeg") else ext
        img_data = f"data:image/{mime};base64,{data}"
    else:
        print(f"  warn: {IMAGE_PATH} not found")

    # ── Build row list ────────────────────────────────────────────────────────
    rows = []  # each row: list of (text, color) segments, or None for blank

    rows.append(make_header(GITHUB_USERNAME))
    rows.append(None)
    rows.append(make_kv("OS",     "Windows 11, Android 16"))
    rows.append(make_kv("Uptime", uptime()))
    rows.append(make_kv("IDE",    "VS Code, Antigravity, Notepad"))
    rows.append(None)
    rows.append(make_section("Languages"))
    rows.append(make_kv("Languages.Programming", "Python, C++, C, Java, JS, TS, Dart",   key_width=30))
    rows.append(make_kv("Languages.Computer",    "HTML, CSS, JSON, YAML, SQL, Bash, PS, Git", key_width=30))
    rows.append(None)
    rows.append(make_section("Hobbies"))
    rows.append(make_kv("Hobbies.Software", "Competitive Programming, Editing, Gaming, Anime", key_width=26))
    rows.append(make_kv("Hobbies.Hardware", "Football, Running",                               key_width=26))
    rows.append(None)
    rows.append(make_section("Contact"))
    rows.append(make_kv("Email",     "jeeva.mail10@gmail.com"))
    rows.append(make_kv("LinkedIn",  "jeevapriyan11"))
    rows.append(make_kv("Twitter",   "jeevapriyan10"))
    rows.append(make_kv("Instagram", "ft.jeevz_"))
    rows.append(make_kv("Telegram",  "jeevapriyan10"))
    rows.append(None)
    rows.append(make_section("GitHub Stats"))
    rows.append(make_kv("Repos",     fmt(stats["repos"])))
    rows.append(make_kv("Commits",   fmt(stats["commits"])))
    rows.append(make_kv("Stars",     fmt(stats["stars"])))
    rows.append(make_kv("Followers", fmt(stats["followers"])))
    rows.append(make_kv_multi("Lines of Code", [
        (fmt(stats["loc_net"]),        VALUE_C),
        ("  (",                        VALUE_C),
        (f"+{fmt(stats['loc_add'])}",  GREEN_C),
        (", ",                         VALUE_C),
        (f"-{fmt(stats['loc_del'])}",  RED_C),
        (")",                          VALUE_C),
    ]))

    # ── Dimensions ────────────────────────────────────────────────────────────
    n_rows  = len(rows)
    txt_h   = n_rows * LINE_H + SVG_PAD
    img_h   = txt_h - SVG_PAD * 2 + 10

    text_block_w = int(LINE_CHARS * CHAR_W) + 20
    SVG_W = IMG_W + IMG_PAD * 2 + text_block_w + SVG_PAD
    SVG_H = txt_h + SVG_PAD * 2

    start_y = SVG_PAD + LINE_H   # first line baseline
    tx      = IMG_W + IMG_PAD * 2   # text X start

    # ── SVG elements ──────────────────────────────────────────────────────────
    els = []
    els.append(f'<rect width="{SVG_W}" height="{SVG_H}" fill="{BG}" rx="8"/>')

    if img_data:
        els.append(
            f'<defs><clipPath id="ic">'
            f'<rect x="{IMG_PAD}" y="{SVG_PAD}" '
            f'width="{IMG_W}" height="{img_h}" rx="6"/>'
            f'</clipPath></defs>'
        )
        els.append(
            f'<image href="{img_data}" '
            f'x="{IMG_PAD}" y="{SVG_PAD}" '
            f'width="{IMG_W}" height="{img_h}" '
            f'preserveAspectRatio="xMidYMid slice" clip-path="url(#ic)"/>'
        )

    for i, row in enumerate(rows):
        y = start_y + i * LINE_H
        if row is None:
            continue
        els.append(render_line_segs(row, tx, y))

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{SVG_W}" height="{SVG_H}" viewBox="0 0 {SVG_W} {SVG_H}">\n'
        + "\n".join(f"  {e}" for e in els)
        + "\n</svg>"
    )
    return svg

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    stats = fetch_stats()
    print(f"  repos={stats['repos']} commits={stats['commits']} "
          f"stars={stats['stars']} loc_net={stats['loc_net']:,}")
    OUTPUT_PATH.write_text(build_svg(stats), encoding="utf-8")
    print(f"Written → {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
