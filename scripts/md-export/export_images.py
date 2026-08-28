# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Export mermaid diagrams and tables from a rendered HTML file as PNG images.

Uses Playwright to open the HTML in a headless browser, waits for mermaid
to render client-side, then screenshots each diagram and table element.

Usage:
    uv run python md-export-utils/export_images.py <html_file> [--output-dir <dir>] [--width <px>]

Examples:
    # Export from Markdown Preview Enhanced HTML output
    uv run python md-export-utils/export_images.py blog/exported.html

    # Custom output directory and viewport width
    uv run python md-export-utils/export_images.py blog/exported.html --output-dir blog/images --width 1600

Prerequisites:
    uv add playwright
    uv run playwright install chromium
"""
import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export mermaid diagrams and tables from rendered HTML as PNG images."
    )
    parser.add_argument("html_file", help="Path to the rendered HTML file")
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help="Output directory for PNG files (default: <html_dir>/images)",
    )
    parser.add_argument(
        "--width", "-w",
        type=int,
        default=1400,
        help="Browser viewport width in pixels (default: 1400)",
    )
    parser.add_argument(
        "--wait", "-t",
        type=int,
        default=5000,
        help="Milliseconds to wait for mermaid rendering (default: 5000)",
    )
    parser.add_argument(
        "--mermaid-selector",
        default="div.mermaid",
        help="CSS selector for mermaid diagram containers (default: div.mermaid)",
    )
    parser.add_argument(
        "--table-selector",
        default="table",
        help="CSS selector for tables (default: table)",
    )
    return parser.parse_args()


def export_images(
    html_file: str,
    output_dir: str,
    width: int = 1400,
    wait_ms: int = 5000,
    mermaid_selector: str = "div.mermaid",
    table_selector: str = "table",
):
    html_path = Path(html_file).resolve()
    if not html_path.exists():
        print(f"ERROR: HTML file not found: {html_path}")
        sys.exit(1)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    html_url = html_path.as_uri()
    print(f"Opening: {html_url}")
    print(f"Output:  {out_dir.resolve()}")
    print(f"Viewport width: {width}px")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": 900})
        page.goto(html_url)

        print(f"Waiting {wait_ms}ms for mermaid diagrams to render...")
        page.wait_for_timeout(wait_ms)

        # Export mermaid diagrams
        mermaid_els = page.query_selector_all(mermaid_selector)
        print(f"\nFound {len(mermaid_els)} mermaid diagrams")
        for i, el in enumerate(mermaid_els):
            out_path = out_dir / f"diagram-{i + 1:02d}.png"
            el.screenshot(path=str(out_path))
            print(f"  [{i + 1}] {out_path.name}")

        # Export tables
        table_els = page.query_selector_all(table_selector)
        print(f"\nFound {len(table_els)} tables")
        for i, el in enumerate(table_els):
            out_path = out_dir / f"table-{i + 1:02d}.png"
            el.screenshot(path=str(out_path))
            print(f"  [{i + 1}] {out_path.name}")

        browser.close()

    total = len(mermaid_els) + len(table_els)
    print(f"\nDone! {total} images saved to {out_dir.resolve()}")
    return len(mermaid_els), len(table_els)


def main():
    args = parse_args()
    output_dir = args.output_dir or str(Path(args.html_file).parent / "images")
    export_images(
        html_file=args.html_file,
        output_dir=output_dir,
        width=args.width,
        wait_ms=args.wait,
        mermaid_selector=args.mermaid_selector,
        table_selector=args.table_selector,
    )


if __name__ == "__main__":
    main()
