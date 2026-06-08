```python
#!/usr/bin/env python3

from datetime import date
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

OUTPUT_PATH = Path("personal_mode.svg")

BIRTHDAY = date(2007, 1, 19)

# ─────────────────────────────────────────────────────────────
# COLORS
# ─────────────────────────────────────────────────────────────

BG        = "#0d1117"
HEADER_C  = "#58a6ff"
LABEL_C   = "#58a6ff"
VALUE_C   = "#e6edf3"
DOT_C     = "#3d444d"
LINE_C    = "#21262d"

# ─────────────────────────────────────────────────────────────
# FONT
# ─────────────────────────────────────────────────────────────

FONT      = "Fira Code, Cascadia Code, Consolas, monospace"

FS        = 14
LINE_H    = 24
CHAR_W    = 8.2

SVG_PAD_X = 28
SVG_PAD_Y = 26

LINE_W    = 78

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def esc(s):
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )

def calculate_age():
    today = date.today()

    years = today.year - BIRTHDAY.year
    months = today.month - BIRTHDAY.month
    days = today.day - BIRTHDAY.day

    if days < 0:
        months -= 1
        days += 30

    if months < 0:
        years -= 1
        months += 12

    return f"{years} years, {months} months, {days} days"

def build_line(label="", value="", indent=False):

    prefix = "  " if indent else ""

    left = f"{prefix}{label}"

    remaining = LINE_W - len(left) - len(value)

    if remaining < 2:
        remaining = 2

    dots = "─" * remaining

    return [
        (left, LABEL_C),
        (dots, LINE_C),
        (value, VALUE_C),
    ]

def raw_line(text):
    return [(text, VALUE_C)]

def divider():
    return [("─" * LINE_W, LINE_C)]

def render_line(segments, x, y):

    tspans = []

    for text, color in segments:
        tspans.append(
            f'<tspan fill="{color}">{esc(text)}</tspan>'
        )

    joined = "".join(tspans)

    return (
        f'<text x="{x}" y="{y}" '
        f'font-family="{FONT}" '
        f'font-size="{FS}" '
        f'xml:space="preserve">'
        f'{joined}'
        f'</text>'
    )

# ─────────────────────────────────────────────────────────────
# CONTENT
# ─────────────────────────────────────────────────────────────

uptime = calculate_age()

rows = []

rows.append(
    raw_line('My Profile/ver. 1.0.0: "Still looking for the One Piece."')
)

rows.append(divider())

rows.append(build_line("Name:              ", "JEEVA PRIYAN R"))
rows.append(build_line("Pronouns:          ", "He/Him"))
rows.append(build_line("WhoAmI:            ", "Developer & Anime & Sports & Cinephile"))
rows.append(build_line("Status:            ", "Finding the One Piece"))
rows.append(build_line("Uptime:            ", uptime))
rows.append(build_line("Location:          ", "Chennai, India"))

rows.append(divider())

rows.append(build_line(
    "Hobbies.Software:  ",
    "Competitive Programming · Editing · Anime · Gaming"
))

rows.append(build_line(
    "Hobbies.Hardware:  ",
    "Football · Running"
))

rows.append(divider())

rows.append(build_line("Fav.Anime(1):      ", "One Piece"))
rows.append(build_line("Fav.Anime(2):      ", "Oregairu"))

rows.append(build_line(
    "Fav.Personalities: ",
    "Sanji && Spiderman"
))

rows.append(build_line(
    "                   ",
    "&& Shanks && Hachiman Hikigaya"
))

rows.append(build_line("Fav.Song:          ", "Love Me — JMSN"))
rows.append(build_line(
    "Fav.Equation:      ",
    'Murphy\'s Law - "Whatever can happen, will happen."'
))

rows.append(divider())

rows.append(build_line("Me.Zodiac          ", "Capricorn"))
rows.append(build_line("Me.Height          ", "5'7"))
rows.append(build_line("Me.Idol            ", "Lionel Messi && Virat Kohli"))

# ─────────────────────────────────────────────────────────────
# SVG SIZE
# ─────────────────────────────────────────────────────────────

SVG_W = int(LINE_W * CHAR_W) + SVG_PAD_X * 2
SVG_H = len(rows) * LINE_H + SVG_PAD_Y * 2

# ─────────────────────────────────────────────────────────────
# SVG BUILD
# ─────────────────────────────────────────────────────────────

elements = []

elements.append(
    f'<rect width="{SVG_W}" height="{SVG_H}" fill="{BG}" rx="10"/>'
)

start_x = SVG_PAD_X
start_y = SVG_PAD_Y + LINE_H

for i, row in enumerate(rows):

    y = start_y + (i * LINE_H)

    elements.append(
        render_line(row, start_x, y)
    )

svg = (
    f'<svg xmlns="http://www.w3.org/2000/svg" '
    f'width="{SVG_W}" '
    f'height="{SVG_H}" '
    f'viewBox="0 0 {SVG_W} {SVG_H}">\n'
    +
    "\n".join(elements)
    +
    "\n</svg>"
)

OUTPUT_PATH.write_text(svg, encoding="utf-8")

print(f"Generated {OUTPUT_PATH}")
```
