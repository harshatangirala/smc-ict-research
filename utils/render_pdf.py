"""Render docs/findings_report.html to a PDF via a real browser engine
(Playwright + Chromium), so the PDF matches the published Artifact exactly
-- same fonts, same layout, same print media rules -- rather than being a
separately hand-built document that could drift from it.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_HTML = REPO_ROOT / "docs" / "findings_report.html"
OUTPUT_PDF = REPO_ROOT / "docs" / "findings_report.pdf"


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
