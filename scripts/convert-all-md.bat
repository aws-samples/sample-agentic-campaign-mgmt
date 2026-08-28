@REM Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
@REM SPDX-License-Identifier: MIT-0

@echo off
REM Convert all Markdown files in current directory to Word documents
REM Creates a 'word-exports' folder with all .docx files

echo Converting all .md files to Word documents...
echo.

if not exist "word-exports" mkdir word-exports

set COUNT=0

for %%f in (*.md) do (
    echo Converting %%f...
    pandoc "%%f" -o "word-exports\%%~nf.docx" ^
        --toc ^
        --toc-depth=3

    if %ERRORLEVEL% EQU 0 (
        set /a COUNT+=1
        echo   ✓ Created word-exports\%%~nf.docx
    ) else (
        echo   ✗ Failed to convert %%f
    )
    echo.
)

echo.
echo Completed! Converted %COUNT% files.
echo All Word documents are in: word-exports\
echo.
pause
