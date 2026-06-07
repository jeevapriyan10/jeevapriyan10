#!/usr/bin/env python3
"""
generate_svg.py
Generates dark_mode.svg — a neofetch-style profile card.
Left : your image (assets/me.jpg) encoded as base64.
Right: live GitHub stats + personal info in monospace.
Alignment is pixel-perfect: keys and values are placed at fixed X coordinates.
"""

import os
import base64
import requests
from datetime import date
from pathlib import Path

# ─── CONFIG ───────────────────────────────────────────────────────────────────
GITHUB_USERNAME = "jeevapriyan10"
BIRTHDAY        = date(2007, 1, 19)
TOKEN           = os.environ.get("GITHUB_TOKEN", "")
HEADERS         = {"Authorization": f"token {TOKEN}"} if TOKEN else {}
IMAGE_PATH      = Path("assets/me.jpg")
OUTPUT_PATH     = Path("dark_mode.svg")

# ─── SVG LAYOUT ───────────────────────────────────────────────────────────────
SVG_W       = 980       # total width
SVG_H       = 460       # total height — fits all lines comfortably
PAD         = 24        # outer padding

IMG_X       = PAD
IMG_Y       = PAD
IMG_W       = 260
IMG_H       = SVG_H - PAD * 2

TEXT_BLOCK_X = IMG_X + IMG_W + 28   # where text block starts
KEY_X        = TEXT_BLOCK_X          # key column
DOT_X        = TEXT_BLOCK_X + 180   # dot column (fixed)
VAL_X        = TEXT_BLOCK_X + 220   # value column (fixed)

LINE_H      = 20        # px between lines
START_Y     = PAD + 16  # first line Y
FONT        = "Fira Code, Cascadia Code, Consolas, monospace"
FS          = 12        # font-size px

# ─── COLORS ───────────────────────────────────────────────────────────────────
BG        = "#0d1117"
LABEL_C   = "#58a6ff"   # blue  — keys & section headers
VALUE_C   = "#e6edf3"   # white — values
DOT_C     = "#30363d"   # dark grey — dots
ACCENT_C  = "#3fb950"   # green — added LOC
DELETE_C  = "#f85149"   # red   — deleted LOC
HEADER_C  = "#f78166"   # orange — username
LINE_C    = "#21262d"   # divider dashes

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def esc(s: str) -> str:
    return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def rest(endpoint: str):
    r = requests.get(f"https://api.github.com/{endpoint}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()

def gql(query: str) -> dict:
    r = requests.post("https://api.github.com/graphql",
                      json={"query": query}, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()

def uptime() -> str:
    today  = date.today()
    years  = today.year  - BIRTHDAY.year
    months = today.month - BIRTHDAY.month
    if months < 0:
        years -= 1; months += 12
    return f"{years} years, {months} months"

def fmt(n: int) -> str:
    return f"{n:,}"

# ─── GITHUB DATA ──────────────────────────────────────────────────────────────
def fetch_stats() -> dict:
    print("Fetching GitHub stats...")
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
        print(f"  warn: commits — {e}")

    print("  Counting lines of code...")
    for repo in all_repos:
        try:
            stats = rest(f"repos/{GITHUB_USERNAME}/{repo['name']}/stats/contributors")
            if not isinstance(stats, list): continue
            for c in stats:
                if c.get("author",{}).get("login","").lower() == GITHUB_USERNAME.lower():
                    for w in c.get("weeks",[]):
                        loc_add += w.get("a",0); loc_del += w.get("d",0)
        except Exception:
            pass

    return dict(repos=repos_count, followers=followers, stars=stars,
                commits=commits, loc_add=loc_add, loc_del=loc_del,
                loc_net=loc_add - loc_del)

# ─── IMAGE ────────────────────────────────────────────────────────────────────
def encode_image(path: Path) -> str:
    if not path.exists():
        print(f"  warn: {path} not found"); return ""
    data = base64.b64encode(path.read_bytes()).decode()
    ext  = path.suffix.lower().lstrip(".")
    mime = "jpeg" if ext in ("jpg","jpeg") else ext
    return f"data:image/{mime};base64,{data}"

# ─── SVG BUILDER ──────────────────────────────────────────────────────────────
# Each logical row is one of:
#   ("header", username)
#   ("blank",)
#   ("section", label)
#   ("kv", key, value)
#   ("kv_multi", key, [(segment, color), ...])   ← for LOC line

def build_svg(stats: dict) -> str:
    img_data = encode_image(IMAGE_PATH)
    DASH = "─"; DOT = "·"

    rows = []
    def H(u):     rows.append(("header",  u))
    def B():      rows.append(("blank",))
    def S(lbl):   rows.append(("section", lbl))
    def KV(k, v): rows.append(("kv", k, v))
    def KVM(k, segs): rows.append(("kv_multi", k, segs))

    H(GITHUB_USERNAME)
    B()
    KV("OS",     "Windows 11, Android 16")
    KV("Uptime", uptime())
    KV("IDE",    "VS Code, Antigravity, Notepad")
    B()
    S("Languages")
    KV("Languages.Programming", "Python, C++, C, Java, JS, TS, Dart")
    KV("Languages.Computer",   "HTML, CSS, JSON, YAML, SQL, MongoDB, Bash, PS, Git")
    B()
    S("Hobbies")
    KV("Hobbies.Software", "Competitive Programming, Editing, Gaming, Anime")
    KV("Hobbies.Hardware", "Football, Running")
    B()
    S("Contact")
    KV("Email",     "jeeva.mail10@gmail.com")
    KV("LinkedIn",  "jeevapriyan11")
    KV("Twitter",   "jeevapriyan10")
    KV("Instagram", "ft.jeevz_")
    KV("Telegram",  "jeevapriyan10")
    B()
    S("GitHub Stats")
    KV("Repos",     fmt(stats["repos"]))
    KV("Commits",   fmt(stats["commits"]))
    KV("Stars",     fmt(stats["stars"]))
    KV("Followers", fmt(stats["followers"]))
    KVM("Lines of Code", [
        (f"{fmt(stats['loc_net'])}", VALUE_C),
        ("  (", VALUE_C),
        (f"+{fmt(stats['loc_add'])}", ACCENT_C),
        (", ", VALUE_C),
        (f"-{fmt(stats['loc_del'])}", DELETE_C),
        (")", VALUE_C),
    ])

    # ── Render ────────────────────────────────────────────────────────────────
    el = []   # SVG element strings

    # Background
    el.append(f'<rect width="{SVG_W}" height="{SVG_H}" fill="{BG}" rx="8"/>')

    # Clip path + image
    if img_data:
        el.append(
            f'<defs><clipPath id="ic">'
            f'<rect x="{IMG_X}" y="{IMG_Y}" width="{IMG_W}" height="{IMG_H}" rx="6"/>'
            f'</clipPath></defs>'
        )
        el.append(
            f'<image href="{img_data}" x="{IMG_X}" y="{IMG_Y}" '
            f'width="{IMG_W}" height="{IMG_H}" '
            f'preserveAspectRatio="xMidYMid slice" clip-path="url(#ic)"/>'
        )

    def txt(x, y, text, color, anchor="start", bold=False):
        fw = "600" if bold else "400"
        el.append(
            f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{FS}" '
            f'font-weight="{fw}" fill="{color}" text-anchor="{anchor}" '
            f'xml:space="preserve">{esc(text)}</text>'
        )

    def txt_multi(x, y, segs):
        """Render a line with multiple colored segments using tspan dx."""
        # First segment anchors at x
        parts = []
        for seg_text, seg_color in segs:
            parts.append(f'<tspan fill="{seg_color}">{esc(seg_text)}</tspan>')
        el.append(
            f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{FS}" '
            f'font-weight="400" text-anchor="start" xml:space="preserve">'
            + "".join(parts) + "</text>"
        )

    # dot row between KEY and VAL columns
    DOT_STR = DOT * 18   # fixed dot string — same for every row

    for i, row in enumerate(rows):
        y = START_Y + i * LINE_H

        if row[0] == "blank":
            continue

        elif row[0] == "header":
            dash_str = DASH * 40
            txt(KEY_X, y, f"{row[1]}@dev", HEADER_C, bold=True)
            txt(KEY_X + 110, y, f" {dash_str}", LINE_C)

        elif row[0] == "section":
            dash_str = DASH * 36
            txt(KEY_X, y, "- ", DOT_C)
            txt(KEY_X + 14, y, row[1], LABEL_C, bold=True)
            txt(KEY_X + 14 + len(row[1]) * 7.2, y, f" {dash_str}", LINE_C)

        elif row[0] == "kv":
            _, key, val = row
            txt(KEY_X + 10, y, ".", DOT_C)
            txt(KEY_X + 20, y, key + ":", LABEL_C)
            txt(DOT_X,      y, DOT_STR, DOT_C)
            txt(VAL_X,      y, val, VALUE_C)

        elif row[0] == "kv_multi":
            _, key, segs = row
            txt(KEY_X + 10, y, ".", DOT_C)
            txt(KEY_X + 20, y, key + ":", LABEL_C)
            txt(DOT_X,      y, DOT_STR, DOT_C)
            txt_multi(VAL_X, y, segs)

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{SVG_W}" height="{SVG_H}" viewBox="0 0 {SVG_W} {SVG_H}">\n'
        + "\n".join(f"  {e}" for e in el)
        + "\n</svg>"
    )
    return svg

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    stats = fetch_stats()
    print(f"  repos={stats['repos']}  commits={stats['commits']}  "
          f"stars={stats['stars']}  LOC net={stats['loc_net']:,}")
    OUTPUT_PATH.write_text(build_svg(stats), encoding="utf-8")
    print(f"Written → {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
