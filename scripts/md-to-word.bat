@REM Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
@REM SPDX-License-Identifier: MIT-0

@echo off
REM Convert Markdown to Word Document
REM Usage: md-to-word.bat input.md [output.docx]

if "%~1"=="" (
    echo Usage: md-to-word.bat input.md [output.docx]
    echo Example: md-to-word.bat requirements.md requirements.docx
    exit /b 1
)

set INPUT=%~1
set OUTPUT=%~2

REM If no output specified, use same name with .docx extension
if "%OUTPUT%"=="" (
    set OUTPUT=%~n1.docx
)

echo Converting %INPUT% to %OUTPUT%...

pandoc "%INPUT%" -o "%OUTPUT%" ^
    --toc ^
    --toc-depth=3

if %ERRORLEVEL% EQU 0 (
    echo ✓ Successfully created %OUTPUT%
    start "" "%OUTPUT%"
) else (
    echo ✗ Conversion failed
)
