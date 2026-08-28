# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Replace mermaid code blocks and markdown tables in a .md file with image references.

Scans the markdown file for ```mermaid ... ``` blocks and markdown tables,
replaces each with an ![alt](images/filename.png) reference.

Usage:
    uv run python md-export-utils/replace_with_images.py <md_file> [--image-dir <relative_path>] [--dry-run]

Examples:
    # Preview changes without modifying the file
    uv run python md-export-utils/replace_with_images.py blog/blog-v1.md --dry-run

    # Apply replacements with custom image path
    uv run python md-export-utils/replace_with_images.py blog/blog-v1.md --image-dir images

    # Pipe output to a new file instead of modifying in-place
    uv run python md-export-utils/replace_with_images.py blog/blog-v1.md --dry-run > blog/blog-medium.md
"""
import argparse
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Replace mermaid blocks and markdown tables with image references."
    )
    parser.add_argument("md_file", help="Path to the markdown file")
    parser.add_argument(
        "--image-dir",
        default="images",
        help="Relative path prefix for image references (default: images)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the result to stdout instead of modifying the file",
    )
    parser.add_argument(
        "--diagram-names",
        nargs="*",
        default=None,
        help="Custom names for diagrams (in order). If not provided, uses diagram-01, diagram-02, ...",
    )
    parser.add_argument(
        "--table-names",
        nargs="*",
        default=None,
        help="Custom names for tables (in order). If not provided, uses table-01, table-02, ...",
    )
    return parser.parse_args()


def replace_mermaid_blocks(content: str, image_dir: str, names: list = None) -> tuple:
    """Replace ```mermaid ... ``` blocks with image references."""
    pattern = re.compile(r"```mermaid\n.*?```", re.DOTALL)
    matches = list(pattern.finditer(content))
    count = 0

    for i, match in enumerate(reversed(matches)):
        idx = len(matches) - 1 - i  # original index
        name = names[idx] if names and idx < len(names) else f"diagram-{idx + 1:02d}"
        replacement = f"![{name}]({image_dir}/{name}.png)"
        content = content[: match.start()] + replacement + content[match.end() :]
        count += 1

    return content, count


def replace_markdown_tables(content: str, image_dir: str, names: list = None) -> tuple:
    """Replace markdown tables (header + separator + rows) with image references."""
    # Match tables: line starting with |, followed by |---| separator, followed by more | rows
    pattern = re.compile(
        r"^(\|[^\n]+\|\n\|[\s\-:|]+\|\n(?:\|[^\n]+\|\n)*\|[^\n]+\|)",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(content))
    count = 0

    for i, match in enumerate(reversed(matches)):
        idx = len(matches) - 1 - i
        name = names[idx] if names and idx < len(names) else f"table-{idx + 1:02d}"
        replacement = f"![{name}]({image_dir}/{name}.png)"
        content = content[: match.start()] + replacement + content[match.end() :]
        count += 1

    return content, count


def main():
    args = parse_args()
    md_path = Path(args.md_file)

    if not md_path.exists():
        print(f"ERROR: File not found: {md_path}")
        sys.exit(1)

    content = md_path.read_text(encoding="utf-8")
    original = content

    content, diagram_count = replace_mermaid_blocks(
        content, args.image_dir, args.diagram_names
    )
    content, table_count = replace_markdown_tables(
        content, args.image_dir, args.table_names
    )

    if args.dry_run:
        print(content)
        print(f"\n# --- DRY RUN ---", file=sys.stderr)
        print(f"# Would replace {diagram_count} mermaid blocks + {table_count} tables", file=sys.stderr)
    else:
        if content != original:
            md_path.write_text(content, encoding="utf-8")
            print(f"Updated {md_path}: replaced {diagram_count} mermaid blocks + {table_count} tables")
        else:
            print(f"No changes needed in {md_path}")


if __name__ == "__main__":
    main()
