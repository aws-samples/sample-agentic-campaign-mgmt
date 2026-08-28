<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: MIT-0 -->

# md-export

Utilities for exporting a markdown blog post (with mermaid diagrams and tables) into a format suitable for platforms like Medium that don't support these features natively.

## The Problem

Platforms like Medium strip mermaid diagrams, markdown tables, and most HTML tags. If your blog uses these features, you need to convert them to images before publishing.

## Workflow

```
┌─────────────────────────┐
│  1. Write blog in .md   │  blog-v1.md (mermaid + tables)
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│  2. Export to HTML       │  VSCode → Markdown Preview Enhanced
│     (offline)            │  Right-click preview → Export → HTML → HTML (offline)
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│  3. Screenshot elements  │  export_images.py
│     from rendered HTML   │  Opens HTML in headless Chrome, screenshots each
│                          │  mermaid diagram and table as PNG
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│  4. Replace in markdown  │  replace_with_images.py
│     mermaid → ![img]     │  Replaces ```mermaid blocks and | tables |
│     tables → ![img]      │  with ![alt](images/name.png) references
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│  5. Publish              │  Paste into Medium / dev.to / Hashnode
│                          │  Drag-and-drop images where needed
└─────────────────────────┘
```

## Setup (one-time)

```bash
# Install playwright (from your project root)
uv add playwright

# Install Chromium browser
uv run playwright install chromium
```

## Step-by-Step

### Step 1: Export your markdown to HTML

In VSCode with Markdown Preview Enhanced:
1. Open your `.md` file
2. Open the preview (Ctrl+Shift+V or the preview icon)
3. Right-click the preview → **Export** → **HTML** → **HTML (offline)**
4. Note the output path (usually a temp file)

### Step 2: Export diagrams and tables as PNGs

```bash
# Basic usage — exports to <html_dir>/images/
uv run python scripts/md-export/export_images.py path/to/exported.html

# Custom output directory
uv run python scripts/md-export/export_images.py path/to/exported.html --output-dir blog/images

# Wider viewport for large diagrams
uv run python scripts/md-export/export_images.py path/to/exported.html --width 1600

# More wait time if mermaid diagrams are complex
uv run python scripts/md-export/export_images.py path/to/exported.html --wait 8000
```

Output:
```
Found 8 mermaid diagrams
  [1] diagram-01.png
  [2] diagram-02.png
  ...
Found 7 tables
  [1] table-01.png
  [2] table-02.png
  ...
Done! 15 images saved to blog/images
```

### Step 3: Replace mermaid blocks and tables in markdown

```bash
# Preview changes first (dry run)
uv run python scripts/md-export/replace_with_images.py blog/blog-v1.md --dry-run

# Apply replacements in-place
uv run python scripts/md-export/replace_with_images.py blog/blog-v1.md --image-dir images

# With custom names for diagrams and tables
uv run python scripts/md-export/replace_with_images.py blog/blog-v1.md \
    --diagram-names manual-workflow sequence-diagram genai-vs-ml feature-importance \
    --table-names tools-table issue-types deployment-options
```

### Step 4: Review and publish

1. Open the updated markdown in preview — verify all images render correctly
2. Copy/paste into Medium's editor, or use Medium's "Import a story" with a hosted HTML version
3. Drag-and-drop any images that didn't paste correctly

## Script Reference

### export_images.py

| Flag | Default | Description |
|------|---------|-------------|
| `html_file` | (required) | Path to the rendered HTML file |
| `--output-dir`, `-o` | `<html_dir>/images` | Output directory for PNG files |
| `--width`, `-w` | `1400` | Browser viewport width in pixels |
| `--wait`, `-t` | `5000` | Milliseconds to wait for mermaid rendering |
| `--mermaid-selector` | `div.mermaid` | CSS selector for mermaid containers |
| `--table-selector` | `table` | CSS selector for tables |

### replace_with_images.py

| Flag | Default | Description |
|------|---------|-------------|
| `md_file` | (required) | Path to the markdown file |
| `--image-dir` | `images` | Relative path prefix for image references |
| `--dry-run` | `false` | Print result to stdout instead of modifying file |
| `--diagram-names` | `diagram-01`, ... | Custom names for diagrams (in order) |
| `--table-names` | `table-01`, ... | Custom names for tables (in order) |

## Tips

- **Image quality:** Increase `--width` for sharper screenshots of wide diagrams. 1400px works for most; use 1600-1800 for large sequence diagrams or wide tables.
- **Dark theme:** The screenshots inherit the theme from your Markdown Preview Enhanced settings. Switch to a light theme before exporting if your blog will be on a white background.
- **Naming:** Use `--diagram-names` and `--table-names` for descriptive filenames instead of generic `diagram-01.png`. Makes the markdown more readable and images easier to find.
- **Medium image upload:** Medium doesn't load local image paths. After pasting your markdown, drag-and-drop each image from your `images/` folder into the Medium editor at the correct position.
- **Alternative platforms:** dev.to renders mermaid natively and supports markdown tables — you may not need this export step at all. Consider cross-posting to Medium with a canonical URL pointing to dev.to.
