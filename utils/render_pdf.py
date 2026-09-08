"""Render the standalone findings HTML page to a PDF via Playwright + Chromium.

SUPERSEDED. The page this renders was generated from the pre-correction
pipeline and now lives in docs/superseded/ -- see that directory's README for
what it gets wrong. The paths below point there so the script still runs, but
the output should not be published.

For the current paper use ``tools/build_manuscript_pdf.py``, which renders
docs/manuscript.md and needs only a Chrome/Chromium/Edge binary rather than a
Playwright install.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_HTML = REPO_ROOT / "docs" / "superseded" / "findings_report.html"
OUTPUT_PDF = REPO_ROOT / "docs" / "superseded" / "findings_report.pdf"


def render() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(SOURCE_HTML.as_uri())
        page.wait_for_timeout(300)  # let @font-face/layout settle
        page.emulate_media(media="print")
        page.pdf(
            path=str(OUTPUT_PDF),
            format="A4",
            print_background=True,
            margin={"top": "16mm", "bottom": "16mm", "left": "14mm", "right": "14mm"},
        )
        browser.close()
    print(f"Wrote {OUTPUT_PDF} ({OUTPUT_PDF.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    render()
