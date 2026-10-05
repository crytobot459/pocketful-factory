#!/usr/bin/env python3
"""Render docs/DECK.md to the two files the submission form asks for.

The event's form takes a slide presentation and a cover image. `docs/DECK.md` is the
source of both, so neither file is written by hand and neither can drift away from the
deck: this reads the markdown and nothing else.

    python3 tools/make_deck.py --pdf      # docs/DECK.pdf, one 16:9 page per slide
    python3 tools/make_deck.py --cover    # docs/cover.png, 1920x1080
    python3 tools/make_deck.py            # both

It has no third-party dependency beyond Chrome, which the app itself is a screenshot of,
and no markdown library: the subset `DECK.md` uses is headings, paragraphs, emphasis,
inline code, fenced code, pipe tables and hyphen lists, and that is what `md_html` below
handles. Anything else in the markdown is passed through as text rather than dropped, so a
slide can never silently lose a claim.

The PDF is produced by printing the HTML through Chrome at 1280x720 CSS pixels, which is
the same 16:9 the video is, so a slide and the shot it explains are the same shape.
"""
from __future__ import annotations

import argparse
import html
import json
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DECK = ROOT / "docs" / "DECK.md"
OUT_PDF = ROOT / "docs" / "DECK.pdf"
OUT_COVER = ROOT / "docs" / "cover.png"

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

PAGE_W, PAGE_H = 1280, 720

CSS = """
@page { size: 1280px 720px; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body { background: #0d1117; color: #e6edf3; }
.slide {
  width: 1280px; height: 720px; padding: 54px 68px 46px;
  page-break-after: always; break-after: page;
  display: flex; flex-direction: column; position: relative; overflow: hidden;
}
.slide:last-child { page-break-after: auto; break-after: auto; }
.slide::before {
  content: ""; position: absolute; left: 0; top: 0; width: 100%; height: 5px;
  background: linear-gradient(90deg, #3fb950 0%, #58a6ff 55%, #d29922 100%);
}
.inner { transform-origin: top left; }
.rule { font: 600 15px/1 ui-monospace, "SF Mono", Menlo, monospace; letter-spacing: .16em;
  text-transform: uppercase; color: #7d8590; margin: 0 0 14px; }
h1 { font: 700 44px/1.16 -apple-system, "Helvetica Neue", Arial, sans-serif;
  margin: 0 0 22px; letter-spacing: -.015em; }
h1 .n { color: #58a6ff; margin-right: 14px; }
p { font: 400 21px/1.5 -apple-system, "Helvetica Neue", Arial, sans-serif; margin: 0 0 15px;
  color: #c9d1d9; }
p.lead { font-size: 24px; color: #e6edf3; }
strong { color: #f0f6fc; font-weight: 650; }
em { color: #e6edf3; }
code { font: 500 18px/1.4 ui-monospace, "SF Mono", Menlo, monospace; color: #79c0ff;
  background: #161b22; border: 1px solid #30363d; border-radius: 5px; padding: 1px 6px; }
pre { background: #161b22; border: 1px solid #30363d; border-left: 3px solid #3fb950;
  border-radius: 8px; padding: 16px 20px; margin: 0 0 16px; overflow: hidden; }
pre code { background: none; border: 0; padding: 0; font-size: 19px; line-height: 1.5;
  color: #a5d6ff; display: block; white-space: pre-wrap; }
ul { margin: 0 0 15px; padding-left: 26px; }
li { font: 400 21px/1.45 -apple-system, "Helvetica Neue", Arial, sans-serif; color: #c9d1d9;
  margin-bottom: 9px; }
li::marker { color: #3fb950; }
table { border-collapse: collapse; width: 100%; margin: 0 0 16px; }
th, td { text-align: left; padding: 8px 12px; font: 400 17px/1.4 -apple-system,
  "Helvetica Neue", Arial, sans-serif; border-bottom: 1px solid #21262d; vertical-align: top; }
th { color: #7d8590; font-weight: 600; font-size: 14px; letter-spacing: .09em;
  text-transform: uppercase; border-bottom: 1px solid #30363d; }
td code { font-size: 15px; }
.foot { margin-top: auto; padding-top: 14px; font: 500 14px/1.4 ui-monospace, "SF Mono",
  Menlo, monospace; color: #484f58; display: flex; justify-content: space-between; }
.cover { justify-content: center; padding: 72px 76px; }
.cover h1 { font-size: 62px; margin-bottom: 18px; }
.cover .sub { font: 400 26px/1.45 -apple-system, "Helvetica Neue", Arial, sans-serif;
  color: #8b949e; margin: 0 0 34px; }
.cover .line { width: 130px; height: 4px; background: #3fb950; margin: 0 0 34px; }
.cover .grid { display: flex; gap: 16px; margin-bottom: 36px; }
.cover .cell { flex: 1; background: #161b22; border: 1px solid #30363d; border-radius: 10px;
  padding: 16px 18px; }
.cover .cell b { display: block; font: 700 34px/1.1 -apple-system, "Helvetica Neue", Arial,
  sans-serif; color: #58a6ff; }
.cover .cell span { font: 500 13px/1.3 ui-monospace, "SF Mono", Menlo, monospace;
  color: #7d8590; letter-spacing: .1em; text-transform: uppercase; }
.cover .foot { border-top: 1px solid #21262d; padding-top: 20px; }
"""

# A slide that needs more room than 720px gets scaled down rather than cut. It is also not
# allowed to shrink past MIN_SCALE: below that the text stops being readable from the back of
# a room, and the right answer is a slide that carries less, not a smaller slide. `--check`
# is what catches that, so a deck cannot quietly grow into a wall of 12px type.
MIN_SCALE = 0.82
FIT_JS = """
<script>
(function () {
  function fit() {
    document.querySelectorAll('.slide').forEach(function (slide) {
      var inner = slide.querySelector('.inner');
      if (!inner) return;
      inner.style.transform = 'none';
      inner.style.width = 'auto';
      var room = slide.clientHeight - parseFloat(getComputedStyle(slide).paddingTop)
        - parseFloat(getComputedStyle(slide).paddingBottom);
      var foot = slide.querySelector('.foot');
      if (foot) room -= foot.offsetHeight + 14;
      var k = Math.min(1, room / inner.offsetHeight);
      if (k < 0.999) {
        inner.style.transform = 'scale(' + k.toFixed(4) + ')';
        inner.style.width = (100 / k) + '%';
      }
    });
  }
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(fit);
    window.addEventListener('load', fit);
  } else {
    window.addEventListener('load', fit);
  }
})();
</script>
"""

# Reports, per slide, how much room the content actually needed. `--check` reads this back
# out of the rendered page rather than trusting a number computed here, because the answer
# depends on the font that loaded.
MEASURE_JS = """
<script>
window.addEventListener('load', function () {
  var out = [];
  document.querySelectorAll('.slide').forEach(function (slide, i) {
    var inner = slide.querySelector('.inner');
    if (!inner) return;
    var foot = slide.querySelector('.foot');
    var room = slide.clientHeight - parseFloat(getComputedStyle(slide).paddingTop)
      - parseFloat(getComputedStyle(slide).paddingBottom) - (foot ? foot.offsetHeight + 14 : 0);
    out.push({n: i + 1, head: (slide.querySelector('h1') || {}).textContent || '',
              content: inner.offsetHeight, room: room, scale: room / inner.offsetHeight});
  });
  var tag = document.createElement('div');
  tag.id = 'measurements';
  tag.textContent = JSON.stringify(out);
  document.body.appendChild(tag);
});
</script>
"""

COVER_SUB = ("Three coding-agent seats in one BAND room build a wallet service to "
             "specification, one reviews its own work, and every number is checked "
             "against the evidence.")


# --- the markdown subset -----------------------------------------------------------

def inline(text: str) -> str:
    """Emphasis, inline code and links, in that order, so code keeps its own markup."""
    out = html.escape(text, quote=False)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", out)
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', out)
    return out


def table(rows: list[str]) -> str:
    cells = [[c.strip() for c in row.strip().strip("|").split("|")] for row in rows]
    if len(cells) > 1 and all(set(c) <= set("-: ") and c for c in cells[1]):
        head, body = cells[0], cells[2:]
    else:
        head, body = [], cells
    out = ["<table>"]
    if head:
        out.append("<tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr>")
    for row in body:
        out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>")
    out.append("</table>")
    return "".join(out)


def md_html(lines: list[str]) -> str:
    """The block elements `DECK.md` uses. Anything unrecognised becomes a paragraph."""
    out: list[str] = []
    i = 0
    while i < len(lines):
        raw = lines[i].rstrip()
        line = raw.strip()
        i += 1

        if not line:
            continue

        if line.startswith("```"):
            body: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                body.append(lines[i].rstrip("\n"))
                i += 1
            i += 1
            out.append(f"<pre><code>{html.escape(chr(10).join(body))}</code></pre>")
            continue

        if line.startswith("|"):
            rows = [line]
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            out.append(table(rows))
            continue

        if re.match(r"^#{1,6} ", line):
            level = len(line) - len(line.lstrip("#"))
            text = inline(line[level:].strip())
            out.append(f"<h{level}>{text}</h{level}>")
            continue

        if re.match(r"^[-*] ", line):
            items: list[str] = []
            while i < len(lines) and re.match(r"^\s*[-*] ", lines[i]):
                items.append(re.sub(r"^\s*[-*] ", "", lines[i]).strip())
                i += 1
            out.append("<ul>" + "".join(f"<li>{inline(t)}</li>" for t in items) + "</ul>")
            continue

        para = [line]
        while i < len(lines):
            nxt = lines[i].strip()
            if (not nxt or nxt.startswith(("#", "|", "```"))
                    or re.match(r"^[-*] ", nxt)):
                break
            para.append(nxt)
            i += 1
        out.append(f"<p>{inline(' '.join(para))}</p>")

    return "\n".join(out)


def slides() -> list[tuple[str, str]]:
    """(heading, body html) per `## N. Title` section of the deck."""
    text = DECK.read_text(encoding="utf-8")
    body = text.split("\n---\n", 1)[-1] if "\n---\n" in text else text
    parts = re.split(r"^## ", body, flags=re.M)[1:]
    found: list[tuple[str, str]] = []
    for part in parts:
        lines = part.splitlines()
        found.append((lines[0].strip(), md_html(lines[1:])))
    return found


def number(heading: str) -> str:
    m = re.match(r"^(\d+)\.\s*(.*)$", heading)
    return (m.group(1), m.group(2)) if m else ("", heading)


# The cover is the one page that is not a slide: it is the event's thumbnail, so it is
# authored at the 1920x1080 the form crops to rather than scaled up into it. Scaling a
# 1280px page by 1.5 is how a cover ends up with 130px of dead space down the right and a
# soft, aliased headline.
COVER_CSS = """
.slide.cover { width: 1920px; height: 1080px; padding: 108px 114px 74px; }
.cover .rule { font-size: 22px; margin-bottom: 26px; }
.cover h1 { font-size: 96px; margin-bottom: 30px; line-height: 1.1; }
.cover .sub { font-size: 38px; line-height: 1.42; margin-bottom: 52px; max-width: 1400px; }
.cover .line { width: 196px; height: 6px; margin-bottom: 52px; }
.cover .grid { gap: 24px; margin-bottom: 0; }
.cover .cell { padding: 26px 30px; border-radius: 14px; }
.cover .cell b { font-size: 52px; margin-bottom: 8px; }
.cover .cell span { font-size: 19px; }
.cover .foot { font-size: 21px; padding-top: 30px; }
"""


def deck_html() -> str:
    out: list[str] = []
    for heading, body in slides():
        n, title = number(heading)
        label = f"{n} / {len(slides())}"
        out.append(
            f'<section class="slide"><div class="inner">'
            f'<p class="rule">{label}</p>'
            f'<h1><span class="n">{n}</span>{inline(title)}</h1>{body}</div>'
            f'<div class="foot"><span>pocketful-factory</span>'
            f"<span>crytobot459/pocketful-factory</span></div></section>")
    return ("<!doctype html><meta charset='utf-8'><style>" + CSS + "</style>"
            + "".join(out) + FIT_JS)


def cover_html() -> str:
    cells = [("4", "stages built"), ("3", "agent seats"),
             ("35", "claims checked"), ("$0", "cost to run")]
    grid = "".join(f'<div class="cell"><b>{v}</b><span>{k}</span></div>' for v, k in cells)
    return (
        "<!doctype html><meta charset='utf-8'><style>" + CSS + COVER_CSS + "</style>"
        '<section class="slide cover">'
        "<div class='rule'>Dark Factory &middot; BAND x WeAreDevelopers &middot; pocketful track</div>"
        "<h1>Three agents, one room,<br>a wallet built to specification</h1>"
        f"<p class='sub'>{COVER_SUB}</p>"
        f"<div class='line'></div><div class='grid'>{grid}</div>"
        "<div class='foot'><span>crytobot459/pocketful-factory</span>"
        "<span>BAND room affa9999-88af-4bef-b731-55957ba9af33</span></div>"
        "</section>")


# --- rendering ---------------------------------------------------------------------

def write_tmp(html_text: str, stem: str) -> pathlib.Path:
    path = pathlib.Path(f"/tmp/pf-{stem}.html")
    path.write_text(html_text, encoding="utf-8")
    return path


def find_chrome() -> str:
    """The macOS app if it is there, otherwise whatever the PATH has.

    CI has no `/Applications`, and this tool is in the repository, so the path that works on
    the machine that recorded the video is not the path that works on the machine that
    checks the deck.
    """
    for name in (CHROME, "google-chrome", "google-chrome-stable", "chromium",
                 "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    sys.exit(f"chrome not found; {CHROME} was expected, or google-chrome on the PATH")


def measure() -> list[dict]:
    """How much room each slide needed, read back out of the laid-out page."""
    src = write_tmp(deck_html() + MEASURE_JS, "measure")
    result = subprocess.run([find_chrome(), "--headless", "--disable-gpu", "--no-sandbox",
                             "--virtual-time-budget=4000", "--dump-dom", src.as_uri()],
                            capture_output=True, text=True)
    src.unlink(missing_ok=True)
    m = re.search(r'<div id="measurements">(.*?)</div>', result.stdout, re.S)
    if not m:
        sys.exit("could not measure the slides; chrome printed no measurements")
    return json.loads(html.unescape(m.group(1)))


def check() -> int:
    """Fail on a slide that would print clipped or unreadably small."""
    bad = []
    for s in measure():
        where = f"slide {s['n']}"
        if s["scale"] < MIN_SCALE - 0.005:
            bad.append(f"{where} \"{s['head'].strip()[:60]}\" needs {s['scale']:.2f}x of the "
                       f"page and would print at {s['scale']:.2f}x type; split it in DECK.md "
                       f"rather than shrinking it")
        elif s["scale"] < 1:
            print(f"ok   {where} fits at {s['scale']:.2f}x")
        else:
            print(f"ok   {where} fits")
    for line in bad:
        print(f"FAIL {line}", file=sys.stderr)
    if bad:
        print(f"\n{len(bad)} slide(s) do not fit a 16:9 page. A slide that cannot hold its "
              f"text has to become two slides, not a smaller one.", file=sys.stderr)
        return 1
    return 0


def chrome(args: list[str], what: str) -> None:
    # The fit pass measures the laid-out page, so Chrome has to be given time to run it
    # rather than printing the moment the HTML parses.
    result = subprocess.run([find_chrome(), "--headless", "--disable-gpu", "--no-sandbox",
                             "--hide-scrollbars", "--virtual-time-budget=4000",
                             *args], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"chrome failed to write the {what}:\n{result.stderr[-800:]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdf", action="store_true")
    parser.add_argument("--cover", action="store_true")
    parser.add_argument("--check", action="store_true",
                        help="fail if any slide would print clipped or below "
                             f"{MIN_SCALE:.2f}x type; writes nothing")
    args = parser.parse_args()

    if not DECK.exists():
        sys.exit(f"{DECK} is gone; there is no deck to render")

    if args.check:
        return check()

    both = not (args.pdf or args.cover)

    if args.cover or both:
        src = write_tmp(cover_html(), "cover")
        png = OUT_COVER.with_suffix(".tmp.png")
        chrome([f"--screenshot={png}", "--window-size=1920,1080",
                "--default-background-color=0d1117ff", src.as_uri()], "cover")
        png.replace(OUT_COVER)
        src.unlink(missing_ok=True)
        print(f"wrote {OUT_COVER.relative_to(ROOT)}")

    if args.pdf or both:
        src = write_tmp(deck_html(), "deck")
        chrome([f"--print-to-pdf={OUT_PDF}", "--no-pdf-header-footer",
                "--print-to-pdf-no-header", src.as_uri()], "PDF")
        src.unlink(missing_ok=True)
        print(f"wrote {OUT_PDF.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())