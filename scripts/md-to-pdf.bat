@REM Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
@REM SPDX-License-Identifier: MIT-0

@echo off
REM Convert Markdown to PDF Document
REM Usage: md-to-pdf.bat input.md [output.pdf]
REM Note: Requires LaTeX (recommended) or wkhtmltopdf for PDF generation

if "%~1"=="" (
    echo Usage: md-to-pdf.bat input.md [output.pdf]
    echo Example: md-to-pdf.bat requirements.md requirements.pdf
    echo.
    echo Note: PDF generation requires LaTeX or wkhtmltopdf
    echo   LaTeX (recommended): choco install miktex
    echo   wkhtmltopdf: choco install wkhtmltopdf
    exit /b 1
)

set INPUT=%~1
set OUTPUT=%~2

REM If no output specified, use same name with .pdf extension
if "%OUTPUT%"=="" (
    set OUTPUT=%~n1.pdf
)

echo Converting %INPUT% to %OUTPUT%...

REM Try LaTeX engine first (better quality)
pandoc "%INPUT%" -o "%OUTPUT%" ^
    --pdf-engine=xelatex ^
    --toc ^
    --toc-depth=3 ^
    -V geometry:margin=1in ^
    -V fontsize=11pt

if %ERRORLEVEL% EQU 0 (
    echo ✓ Successfully created %OUTPUT%
    start "" "%OUTPUT%"
) else (
    echo ✗ LaTeX conversion failed, trying alternative method...
    echo.

    REM Fallback to HTML-based PDF (requires wkhtmltopdf)
    pandoc "%INPUT%" -o "%OUTPUT%" ^
        --pdf-engine=wkhtmltopdf ^
        --toc ^
        --toc-depth=3

    if %ERRORLEVEL% EQU 0 (
        echo ✓ Successfully created %OUTPUT% using wkhtmltopdf
        start "" "%OUTPUT%"
    ) else (
        echo ✗ PDF conversion failed
        echo.
        echo Please install a PDF engine:
        echo   LaTeX (recommended): choco install miktex
        echo   wkhtmltopdf:        choco install wkhtmltopdf
    )
)
