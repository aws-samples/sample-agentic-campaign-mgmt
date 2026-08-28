<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: MIT-0 -->

# Document Conversion Scripts

Batch scripts for converting between Word documents (.docx), PDF files (.pdf), and Markdown (.md) files using Pandoc.

## Prerequisites

**Pandoc** must be installed on your system.

### Installing Pandoc

**Windows:**
```bash
# Using Chocolatey
choco install pandoc

# Or download from: https://pandoc.org/installing.html
```

**Verify Installation:**
```bash
pandoc --version
```

### PDF Conversion Requirements

For **Markdown to PDF** conversion, you'll need a PDF engine:

**Option 1: LaTeX (Recommended for best quality)**
```bash
# Using Chocolatey
choco install miktex

# Or download from: https://miktex.org/download
```

**Option 2: wkhtmltopdf (Alternative)**
```bash
# Using Chocolatey
choco install wkhtmltopdf

# Or download from: https://wkhtmltopdf.org/downloads.html
```

**Note:** PDF to Markdown conversion only requires Pandoc.

## Scripts Overview

| Script                 | Purpose                                                      |
| ---------------------- | ------------------------------------------------------------ |
| `word-to-md.bat`       | Convert a single Word document to Markdown                   |
| `md-to-word.bat`       | Convert a single Markdown file to Word                       |
| `pdf-to-md.bat`        | Convert a single PDF document to Markdown                    |
| `md-to-pdf.bat`        | Convert a single Markdown file to PDF                        |
| `convert-all-md.bat`   | Batch convert all Markdown files in a directory to Word      |

## Usage

### 1. Word to Markdown (`word-to-md.bat`)

Converts a Word document to Markdown format, extracting any images to a `media/` folder.

**Syntax:**
```bash
word-to-md.bat input.docx [output.md]
```

**Examples:**
```bash
# Basic conversion (auto-generates output filename)
word-to-md.bat requirements.docx

# Specify output filename
word-to-md.bat requirements.docx project-requirements.md

# Convert from different directory
word-to-md.bat "C:\Documents\report.docx" report.md
```

**Features:**
- Automatically generates output filename if not specified
- Extracts embedded images to `./media` folder
- Uses ATX-style headings (`#`, `##`, `###`)
- No line wrapping for better Git diffs

### 2. Markdown to Word (`md-to-word.bat`)

Converts a Markdown file to a Word document with automatic table of contents.

**Syntax:**
```bash
md-to-word.bat input.md [output.docx]
```

**Examples:**
```bash
# Basic conversion (auto-generates output filename)
md-to-word.bat requirements.md

# Specify output filename
md-to-word.bat requirements.md final-requirements.docx

# Convert from different directory
md-to-word.bat "C:\Projects\docs\README.md" documentation.docx
```

**Features:**
- Automatically generates output filename if not specified
- Includes table of contents (TOC) with 3 levels of depth
- Opens the Word document automatically after conversion
- Preserves formatting, tables, and code blocks

### 3. PDF to Markdown (`pdf-to-md.bat`)

Converts a PDF document to Markdown format, extracting any images to a `media/` folder.

**Syntax:**
```bash
pdf-to-md.bat input.pdf [output.md]
```

**Examples:**
```bash
# Basic conversion (auto-generates output filename)
pdf-to-md.bat report.pdf

# Specify output filename
pdf-to-md.bat report.pdf project-report.md

# Convert from different directory
pdf-to-md.bat "C:\Documents\whitepaper.pdf" whitepaper.md
```

**Features:**
- Automatically generates output filename if not specified
- Extracts embedded images to `./media` folder
- Uses ATX-style headings (`#`, `##`, `###`)
- No line wrapping for better Git diffs

**Important Notes:**
- Conversion quality depends on the source PDF structure
- Best results with text-based PDFs (not scanned images)
- Complex layouts may require manual cleanup
- For scanned PDFs, consider using OCR tools first

### 4. Markdown to PDF (`md-to-pdf.bat`)

Converts a Markdown file to a professional PDF document with automatic table of contents.

**Syntax:**
```bash
md-to-pdf.bat input.md [output.pdf]
```

**Examples:**
```bash
# Basic conversion (auto-generates output filename)
md-to-pdf.bat requirements.md

# Specify output filename
md-to-pdf.bat requirements.md final-requirements.pdf

# Convert from different directory
md-to-pdf.bat "C:\Projects\docs\README.md" documentation.pdf
```

**Features:**
- Automatically generates output filename if not specified
- Includes table of contents (TOC) with 3 levels of depth
- Opens the PDF document automatically after conversion
- Professional formatting with 1-inch margins
- 11pt font size for readability
- Automatic fallback to alternative PDF engine if LaTeX not available

**Requirements:**
- Requires LaTeX (MikTeX) or wkhtmltopdf
- Script automatically tries LaTeX first, then falls back to wkhtmltopdf

### 5. Batch Convert All Markdown (`convert-all-md.bat`)

Converts all `.md` files in the current directory to Word documents.

**Syntax:**
```bash
# Run in the directory containing your .md files
convert-all-md.bat
```

**Example:**
```bash
cd /path/to/your/documentation
./scripts/convert-all-md.bat
```

**Features:**
- Processes all `.md` files in the current directory
- Creates a `word-exports/` folder for output files
- Shows progress for each file conversion
- Displays conversion summary at completion
- Includes table of contents in each document

## Output Details

### Word to Markdown Conversion

- **Format:** GitHub Flavored Markdown
- **Headings:** ATX style (`#`, `##`, `###`)
- **Images:** Extracted to `./media` folder with relative paths
- **Tables:** Preserved in Markdown table syntax
- **Line Wrapping:** Disabled for clean diffs

### Markdown to Word Conversion

- **Format:** Office Open XML (.docx)
- **TOC:** Automatically generated with 3 heading levels
- **Styling:** Default Word styles applied
- **Code Blocks:** Monospace font with background shading

### PDF to Markdown Conversion

- **Format:** GitHub Flavored Markdown
- **Headings:** ATX style (`#`, `##`, `###`)
- **Images:** Extracted to `./media` folder with relative paths
- **Quality:** Depends on source PDF structure (text-based PDFs work best)
- **Line Wrapping:** Disabled for clean diffs

### Markdown to PDF Conversion

- **Format:** PDF (Portable Document Format)
- **Engine:** LaTeX (XeLaTeX) or wkhtmltopdf
- **TOC:** Automatically generated with 3 heading levels
- **Margins:** 1 inch on all sides
- **Font:** 11pt for readability
- **Code Blocks:** Monospace font with proper formatting

## Common Workflows

### Documentation Workflow (Word-based)

```bash
# 1. Start with Word document
word-to-md.bat project-spec.docx

# 2. Edit the Markdown file (version control friendly)
# ... make your changes ...

# 3. Convert back to Word for distribution
md-to-word.bat project-spec.md
```

### Documentation Workflow (PDF-based)

```bash
# 1. Start with PDF document
pdf-to-md.bat whitepaper.pdf

# 2. Edit the Markdown file (version control friendly)
# ... make your changes ...

# 3. Convert to PDF for distribution
md-to-pdf.bat whitepaper.md
```

### Multi-Format Distribution

```bash
# Convert Markdown to multiple formats
md-to-word.bat documentation.md
md-to-pdf.bat documentation.md

# Now you have:
# - documentation.md (source)
# - documentation.docx (editable)
# - documentation.pdf (final distribution)
```

### Batch Export Workflow

```bash
# Export all documentation to Word
cd /path/to/your/docs
./scripts/convert-all-md.bat

# Find all Word files in word-exports/
```

## Troubleshooting

### "Pandoc is not recognized..."

Pandoc is not installed or not in your PATH.

- Install Pandoc from https://pandoc.org/installing.html
- Restart your terminal after installation

### PDF conversion fails with "PDF engine not found"

LaTeX or wkhtmltopdf is not installed.

- Install MikTeX: `choco install miktex`
- Or install wkhtmltopdf: `choco install wkhtmltopdf`
- Restart your terminal after installation

### Poor quality PDF to Markdown conversion

- **Scanned PDFs:** Use OCR software first to create searchable PDFs
- **Complex layouts:** May require manual cleanup after conversion
- **Tables:** Check table formatting in the output Markdown
- **Images:** Verify images are extracted to `./media` folder

### Images not appearing in Markdown

- Check the `./media` folder for extracted images
- Ensure image paths in the Markdown are relative to the file location
- For PDFs, ensure images are embedded (not just displayed)

### Word document formatting issues

- Pandoc uses default Word styles
- For custom styling, create a reference document:
  ```bash
  pandoc input.md -o output.docx --reference-doc=template.docx
  ```

### PDF formatting issues

- Adjust margins in `md-to-pdf.bat`: `-V geometry:margin=0.75in`
- Change font size: `-V fontsize=12pt`
- Use different PDF engine if one fails

### Conversion fails with special characters

- Ensure files are UTF-8 encoded
- Avoid special characters in filenames
- For LaTeX errors, try the wkhtmltopdf fallback

## Advanced Customization

### Modify Pandoc Options

Edit the batch files to customize conversion behavior:

**Add custom CSS for HTML export:**

```batch
pandoc "%INPUT%" -o "%OUTPUT%" --css=style.css
```

**Change TOC depth:**

```batch
pandoc "%INPUT%" -o "%OUTPUT%" --toc --toc-depth=2
```

**Use a custom Word template:**

```batch
pandoc "%INPUT%" -o "%OUTPUT%" --reference-doc=custom-template.docx
```

**Customize PDF margins and layout:**

```batch
pandoc "%INPUT%" -o "%OUTPUT%" ^
    --pdf-engine=xelatex ^
    -V geometry:margin=0.75in ^
    -V geometry:paperwidth=8.5in ^
    -V geometry:paperheight=11in ^
    -V fontsize=12pt ^
    -V mainfont="Arial"
```

**Add PDF metadata:**

```batch
pandoc "%INPUT%" -o "%OUTPUT%" ^
    --pdf-engine=xelatex ^
    -V title="Document Title" ^
    -V author="Your Name" ^
    -V date="\today"
```

**Extract specific pages from PDF to Markdown:**

```batch
# Note: Use external tools like pdftk to extract pages first
pdftk input.pdf cat 1-10 output excerpt.pdf
pdf-to-md.bat excerpt.pdf
```

## File Locations

- **Scripts:** `./scripts/`
- **Media folder:** Created in the same directory as input file
- **Word exports:** Created in `./word-exports/` subdirectory

## Additional Resources

- [Pandoc Manual](https://pandoc.org/MANUAL.html)
- [Pandoc PDF Generation](https://pandoc.org/MANUAL.html#creating-a-pdf)
- [Markdown Guide](https://www.markdownguide.org/)
- [Word Document Styling](https://pandoc.org/MANUAL.html#option--reference-doc)
- [LaTeX Installation (MikTeX)](https://miktex.org/)
- [wkhtmltopdf Documentation](https://wkhtmltopdf.org/)

## Support

For issues or enhancements, update the scripts or refer to the Pandoc documentation.
