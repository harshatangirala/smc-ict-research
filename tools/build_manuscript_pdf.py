"""Render docs/manuscript.md to docs/manuscript.pdf.

Markdown -> HTML (python-markdown) -> PDF (headless Chrome/Edge). A real
browser engine is used rather than a Python PDF library so tables, figures and
page breaks lay out the way a reader sees them, and because a Chromium build is
already present on most machines while a TeX distribution is not.

Figures are embedded as base64 data URIs, so the generated HTML is a single
self-contained file and the PDF cannot silently lose an image.

A pandoc route is documented in docs/replication_guide.md for readers who have
pandoc and LaTeX available; both produce the same content from the same source.
"""

from __future__ import annotations

import base64
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "manuscript.md"
OUT_PDF = ROOT / "docs" / "manuscript.pdf"
FIG_DIR = ROOT / "results" / "figures"

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]

CSS = """
@page { size: A4; margin: 20mm 18mm; }
:root { --ink:#111; --ink2:#444; --muted:#6b6b66; --rule:#d8d7d2; --accent:#2a78d6; }
* { box-sizing: border-box; }
body {
  font-family: "Charter","Georgia","Times New Roman",serif;
  font-size: 10.2pt; line-height: 1.52; color: var(--ink);
  margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
h1,h2,h3,h4 { font-family:"Helvetica Neue",Arial,sans-serif; color:var(--ink); line-height:1.25; }
h1.title { font-size: 19pt; margin: 0 0 4pt; letter-spacing:-0.2pt; }
.byline { color: var(--ink2); font-size: 10pt; margin-bottom: 2pt; }
.dateline { color: var(--muted); font-size: 9pt; margin-bottom: 16pt; }
h1 { font-size: 14pt; margin: 20pt 0 7pt; padding-bottom: 3pt; border-bottom: 1px solid var(--rule); }
h2 { font-size: 11.6pt; margin: 14pt 0 5pt; }
h3 { font-size: 10.4pt; margin: 11pt 0 4pt; color: var(--ink2); }
p { margin: 0 0 7.5pt; text-align: justify; hyphens: auto; }
strong { font-weight: 700; }
em { font-style: italic; }
code, pre { font-family: "SF Mono",Consolas,"Liberation Mono",monospace; }
code { font-size: 8.6pt; background:#f4f4f1; padding:0.5pt 3pt; border-radius:2px; }
pre { background:#f7f7f4; border:1px solid var(--rule); border-left:2.5px solid var(--accent);
      padding:8pt 10pt; font-size:8.2pt; line-height:1.42; overflow-x:auto;
      page-break-inside:avoid; border-radius:2px; }
pre code { background:none; padding:0; font-size:inherit; }
table { border-collapse: collapse; width:100%; margin: 9pt 0 12pt; font-size:8.8pt;
        page-break-inside:avoid; }
th { text-align:left; border-bottom:1.2px solid var(--ink); padding:4pt 6pt;
     font-family:"Helvetica Neue",Arial,sans-serif; font-size:8.2pt;
     text-transform:uppercase; letter-spacing:0.3pt; color:var(--ink2); }
td { border-bottom:1px solid var(--rule); padding:3.6pt 6pt; vertical-align:top; }
tr:last-child td { border-bottom:1px solid var(--ink); }
td:not(:first-child), th:not(:first-child) { text-align:right; }
td:first-child, th:first-child { text-align:left; }
blockquote { margin:8pt 0; padding:6pt 12pt; border-left:2.5px solid var(--accent);
             background:#f7f9fc; color:var(--ink2); }
ul, ol { margin: 0 0 8pt; padding-left: 17pt; }
li { margin-bottom: 3.5pt; }
hr { border:none; border-top:1px solid var(--rule); margin:16pt 0; }
img { max-width:100%; display:block; margin:10pt auto; page-break-inside:avoid; }
.abstract { background:#f7f7f4; border:1px solid var(--rule); border-radius:3px;
            padding:11pt 14pt; margin:0 0 16pt; font-size:9.4pt; line-height:1.5; }
.abstract h4 { margin:0 0 5pt; font-size:8.4pt; text-transform:uppercase;
               letter-spacing:0.6pt; color:var(--muted); }
.abstract p { text-align:justify; margin-bottom:5pt; }
.keywords { font-size:8.8pt; color:var(--ink2); margin-top:7pt; }
h1 { page-break-after: avoid; }
h2, h3 { page-break-after: avoid; }
"""


def _split_front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.index("\n---", 3)
    raw, body = text[3:end], text[end + 4 :]
    meta: dict[str, str] = {}
    key, buf = None, []
    for line in raw.splitlines():
        m = re.match(r"^(\w+):\s*(.*)$", line)
        if m and not line.startswith(" "):
            if key:
                meta[key] = "\n".join(buf).strip()
            key, first = m.group(1), m.group(2).strip()
            buf = [] if first in ("", "|") else [first]
        elif key:
            buf.append(line.strip())
    if key:
        meta[key] = "\n".join(buf).strip()
    # Strip the surrounding quotes YAML uses for values containing ':' -- without
    # this the title renders on the PDF cover with literal quote marks around it.
    for k, v in meta.items():
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            meta[k] = v[1:-1]
    return meta, body


def _embed_images(html: str) -> str:
    """Replace figure references with base64 data URIs."""

    def repl(match: re.Match) -> str:
        path = FIG_DIR / Path(match.group(1)).name
        if not path.exists():
            return ""
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        return f'<img src="data:image/png;base64,{b64}" alt="{path.stem}">'

    return re.sub(r'<img[^>]*src="([^"]+)"[^>]*>', repl, html)


def _find_browser() -> str | None:
    for cand in CHROME_CANDIDATES:
        if Path(cand).exists():
            return cand
    for name in ("google-chrome", "chromium", "chrome", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    return None


def build() -> int:
    if not SRC.exists():
        print(f"{SRC} not found", file=sys.stderr)
        return 1

    meta, body = _split_front_matter(SRC.read_text(encoding="utf-8"))

    # Append the figures as a plate section so the PDF is self-contained.
    figures = sorted(FIG_DIR.glob("fig*.png")) if FIG_DIR.exists() else []
    if figures:
        body += "\n\n# Appendix D. Figure plates\n\n"
        for f in figures:
            caption = f.stem.replace("_", " ").replace("fig", "Figure ", 1)
            body += f"\n**{caption}**\n\n![{f.stem}]({f.name})\n\n"

    html_body = markdown.markdown(
        body,
        extensions=["tables", "fenced_code", "sane_lists", "attr_list", "md_in_html"],
    )
    html_body = _embed_images(html_body)

    abstract = meta.get("abstract", "")
    abstract_html = "".join(
        f"<p>{p.strip()}</p>" for p in re.split(r"\n\s*\n", abstract) if p.strip()
    )
    keywords = meta.get("keywords", "").strip("[]").replace(", ", " · ")

    doc = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{meta.get('title', 'Manuscript')}</title>
<style>{CSS}</style></head><body>
<h1 class="title">{meta.get('title', '')}</h1>
<div class="byline">{meta.get('author', '')}</div>
<div class="dateline">{meta.get('date', '')}</div>
<div class="abstract"><h4>Abstract</h4>{abstract_html}
{f'<div class="keywords"><strong>Keywords:</strong> {keywords}</div>' if keywords else ''}
</div>
{html_body}
</body></html>"""

    browser = _find_browser()
    if browser is None:
        fallback = ROOT / "docs" / "manuscript.html"
        fallback.write_text(doc, encoding="utf-8")
        print(
            f"No Chrome/Chromium/Edge found. Wrote {fallback} instead.\n"
            "Produce the PDF with either:\n"
            f"  <browser> --headless --print-to-pdf={OUT_PDF} {fallback}\n"
            "  pandoc docs/manuscript.md -o docs/manuscript.pdf "
            "--pdf-engine=xelatex --toc -V geometry:margin=1in",
            file=sys.stderr,
        )
        return 2

    with tempfile.TemporaryDirectory() as td:
        tmp_html = Path(td) / "manuscript.html"
        tmp_html.write_text(doc, encoding="utf-8")
        profile = Path(td) / "profile"
        cmd = [
            browser, "--headless", "--disable-gpu", "--no-sandbox",
            "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=10000",
            f"--user-data-dir={profile}",
            f"--print-to-pdf={OUT_PDF}",
            tmp_html.as_uri(),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if not OUT_PDF.exists():
            print(f"PDF was not produced.\n{res.stdout}\n{res.stderr}", file=sys.stderr)
            return 1

    # Keep the HTML beside the PDF: it is the reviewable intermediate.
    (ROOT / "docs" / "manuscript.html").write_text(doc, encoding="utf-8")
    print(f"Wrote {OUT_PDF} ({OUT_PDF.stat().st_size / 1024:.0f} KB) using {Path(browser).name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
