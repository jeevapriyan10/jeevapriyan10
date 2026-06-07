#!/usr/bin/env python3
"""
generate_svg.py
Generates dark_mode.svg — a neofetch-style profile card.
Left side: your image (assets/me.jpg) encoded as base64.
Right side: live GitHub stats + personal info in monospace.

Run via GitHub Actions on a schedule. Requires:
  - GITHUB_TOKEN env var (automatically provided in Actions)
  - assets/me.jpg in the repo root
"""

import os
import sys
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

# ─── SVG DIMENSIONS ───────────────────────────────────────────────────────────
SVG_W       = 900
SVG_H       = 480
IMG_X       = 30
IMG_Y       = 30
IMG_W       = 280
IMG_H       = 420
TEXT_X      = 340
LINE_H      = 22
START_Y     = 50
FONT        = "Fira Code, Cascadia Code, Consolas, monospace"
FONT_SIZE   = 13

# ─── COLORS ───────────────────────────────────────────────────────────────────
BG          = "#0d1117"
LABEL_C     = "#58a6ff"    # blue  — keys & section headers
VALUE_C     = "#e6edf3"    # white — values
DOT_C       = "#8b949e"    # grey  — dots / separators
ACCENT_C    = "#3fb950"    # green — added lines of code
DELETE_C    = "#f85149"    # red   — deleted lines of code
HEADER_C    = "#f78166"    # orange — username line
LINE_C      = "#30363d"    # divider lines

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def gql(query: str) -> dict:
    r = requests.post(
        "https://api.github.com/graphql",
        json={"query": query},
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()

def rest(endpoint: str) -> dict | list:
    r = requests.get(
        f"https://api.github.com/{endpoint}",
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()

def uptime() -> str:
    today = date.today()
    years  = today.year - BIRTHDAY.year
    months = today.month - BIRTHDAY.month
    if months < 0:
        years  -= 1
        months += 12
    return f"{years} years, {months} months"

def fmt_num(n: int) -> str:
    return f"{n:,}"

# ─── GITHUB DATA ──────────────────────────────────────────────────────────────
def fetch_stats() -> dict:
    print("Fetching GitHub stats...")

    # Basic user info
    user = rest(f"users/{GITHUB_USERNAME}")
    repos_count  = user.get("public_repos", 0)
    followers    = user.get("followers", 0)
    stars        = 0
    commits      = 0
    loc_add      = 0
    loc_del      = 0

    # Stars across all repos
    page = 1
    all_repos = []
    while True:
        batch = rest(f"users/{GITHUB_USERNAME}/repos?per_page=100&page={page}")
        if not batch:
            break
        all_repos.extend(batch)
        page += 1

    for repo in all_repos:
        stars += repo.get("stargazers_count", 0)

    # Commits (GraphQL — counts contributions to own repos)
    try:
        q = f"""
        {{
          user(login: "{GITHUB_USERNAME}") {{
            contributionsCollection {{
              totalCommitContributions
              restrictedContributionsCount
            }}
          }}
        }}
        """
        data = gql(q)
        cc = data["data"]["user"]["contributionsCollection"]
        commits = (
            cc.get("totalCommitContributions", 0)
            + cc.get("restrictedContributionsCount", 0)
        )
    except Exception as e:
        print(f"  Warning: commit fetch failed: {e}")

    # Lines of code (sum contributor stats across all repos)
    print("  Counting lines of code (this may take a moment)...")
    for repo in all_repos:
        repo_name = repo["name"]
        try:
            contrib_url = f"repos/{GITHUB_USERNAME}/{repo_name}/stats/contributors"
            stats = rest(contrib_url)
            if not isinstance(stats, list):
                continue
            for contributor in stats:
                if contributor.get("author", {}).get("login", "").lower() == GITHUB_USERNAME.lower():
                    for week in contributor.get("weeks", []):
                        loc_add += week.get("a", 0)
                        loc_del += week.get("d", 0)
        except Exception:
            pass

    loc_net = loc_add - loc_del

    return {
        "repos":    repos_count,
        "followers": followers,
        "stars":    stars,
        "commits":  commits,
        "loc_add":  loc_add,
        "loc_del":  loc_del,
        "loc_net":  loc_net,
    }

# ─── IMAGE ENCODE ─────────────────────────────────────────────────────────────
def encode_image(path: Path) -> str:
    if not path.exists():
        print(f"  Warning: {path} not found. Using placeholder.")
        return ""
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    ext = path.suffix.lower().lstrip(".")
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext
    return f"data:image/{mime};base64,{data}"

# ─── SVG BUILDER ──────────────────────────────────────────────────────────────
def build_svg(stats: dict) -> str:
    img_data = encode_image(IMAGE_PATH)

    # ── Build text lines ──────────────────────────────────────────────────────
    DASH = "─"
    DOT  = "·"

    def pad_dots(key: str, total: int = 28) -> str:
        """Return key padded to `total` chars with dots."""
        key_disp = key + ": "
        dots = max(1, total - len(key_disp))
        return key_disp + (DOT * dots) + " "

    def divider(label: str, width: int = 52) -> tuple[str, str, str]:
        """Returns (prefix, label, suffix_dashes) for a section divider."""
        dashes = DASH * (width - len(label) - 3)
        return ("- ", label, f" {dashes}")

    loc_add_str = f"+{fmt_num(stats['loc_add'])}"
    loc_del_str = f"-{fmt_num(stats['loc_del'])}"
    loc_net_str = fmt_num(stats['loc_net'])

    # Each entry: (text, color) or a special tuple for multi-color lines
    # We'll represent lines as a list of (segment_text, color) pairs
    lines: list[list[tuple[str, str]]] = []

    def plain(text: str, color: str = VALUE_C):
        lines.append([(text, color)])

    def kv(key: str, value: str, pad: int = 28):
        lines.append([
            (". ", DOT_C),
            (pad_dots(key, pad), LABEL_C),
            (value, VALUE_C),
        ])

    def section(label: str):
        pre, lbl, suf = divider(label)
        lines.append([
            (pre, DOT_C),
            (lbl, LABEL_C),
            (suf, LINE_C),
        ])

    def blank():
        lines.append([("", VALUE_C)])

    # ── Header ────────────────────────────────────────────────────────────────
    header_dash = DASH * 44
    lines.append([(f"{GITHUB_USERNAME}@dev ", HEADER_C), (header_dash, LINE_C)])
    blank()

    # ── System ────────────────────────────────────────────────────────────────
    kv("OS",     "Windows 11, Android 16")
    kv("Uptime", uptime())
    kv("IDE",    "VS Code, Antigravity, Notepad")
    blank()

    # ── Languages ─────────────────────────────────────────────────────────────
    section("Languages")
    kv("Languages.Programming", "Python, C++, C, Java, JS, TS, Dart", pad=26)
    kv("Languages.Computer",   "HTML, CSS, JSON, YAML, SQL, MongoDB, Bash, PS, Git", pad=26)
    blank()

    # ── Hobbies ───────────────────────────────────────────────────────────────
    section("Hobbies")
    kv("Hobbies.Software", "Competitive Programming, Editing, Gaming, Anime", pad=22)
    kv("Hobbies.Hardware", "Football, Running", pad=22)
    blank()

    # ── Contact ───────────────────────────────────────────────────────────────
    section("Contact")
    kv("Email",     "jeeva.mail10@gmail.com")
    kv("LinkedIn",  "jeevapriyan11")
    kv("Twitter",   "jeevapriyan10")
    kv("Instagram", "ft.jeevz_")
    kv("Telegram",  "jeevapriyan10")
    blank()

    # ── GitHub Stats ──────────────────────────────────────────────────────────
    section("GitHub Stats")
    kv("Repos",         fmt_num(stats["repos"]))
    kv("Commits",       fmt_num(stats["commits"]))
    kv("Stars",         fmt_num(stats["stars"]))
    kv("Followers",     fmt_num(stats["followers"]))

    # Lines of Code — multi-colored
    loc_prefix = [
        (". ", DOT_C),
        (pad_dots("Lines of Code"), LABEL_C),
        (f"{loc_net_str}  (", VALUE_C),
        (loc_add_str, ACCENT_C),
        (", ", VALUE_C),
        (loc_del_str, DELETE_C),
        (")", VALUE_C),
    ]
    lines.append(loc_prefix)

    # ─── Render SVG ──────────────────────────────────────────────────────────
    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"',
        f'     width="{SVG_W}" height="{SVG_H}" viewBox="0 0 {SVG_W} {SVG_H}">',
        f'  <rect width="{SVG_W}" height="{SVG_H}" fill="{BG}" rx="8"/>',
    ]

    # Image
    if img_data:
        svg_lines.append(
            f'  <image href="{img_data}" x="{IMG_X}" y="{IMG_Y}" '
            f'width="{IMG_W}" height="{IMG_H}" '
            f'preserveAspectRatio="xMidYMid meet" '
            f'clip-path="url(#imgClip)"/>'
        )
        svg_lines.insert(3,
            f'  <defs>'
            f'<clipPath id="imgClip">'
            f'<rect x="{IMG_X}" y="{IMG_Y}" width="{IMG_W}" height="{IMG_H}" rx="6"/>'
            f'</clipPath></defs>'
        )

    # Text lines
    for i, line_segs in enumerate(lines):
        y = START_Y + i * LINE_H
        # Build tspan elements
        tspans = ""
        for seg_text, seg_color in line_segs:
            escaped = (seg_text
                       .replace("&", "&amp;")
                       .replace("<", "&lt;")
                       .replace(">", "&gt;")
                       .replace('"', "&quot;"))
            tspans += f'<tspan fill="{seg_color}">{escaped}</tspan>'

        svg_lines.append(
            f'  <text x="{TEXT_X}" y="{y}" '
            f'font-family="{FONT}" font-size="{FONT_SIZE}" '
            f'xml:space="preserve">{tspans}</text>'
        )

    svg_lines.append("</svg>")
    return "\n".join(svg_lines)


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    stats = fetch_stats()
    print(f"  Repos:    {stats['repos']}")
    print(f"  Commits:  {stats['commits']}")
    print(f"  Stars:    {stats['stars']}")
    print(f"  LOC net:  {stats['loc_net']:,}  (+{stats['loc_add']:,} / -{stats['loc_del']:,})")

    svg = build_svg(stats)
    OUTPUT_PATH.write_text(svg, encoding="utf-8")
    print(f"Written → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
