@REM Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
@REM SPDX-License-Identifier: MIT-0

@echo off
REM Convert PDF Document to Markdown
REM Usage: pdf-to-md.bat input.pdf [output.md]

if "%~1"=="" (
    echo Usage: pdf-to-md.bat input.pdf [output.md]
    echo Example: pdf-to-md.bat requirements.pdf requirements.md
    exit /b 1
)

set INPUT=%~1
set OUTPUT=%~2

REM If no output specified, use same name with .md extension
if "%OUTPUT%"=="" (
    set OUTPUT=%~n1.md
)

echo Converting %INPUT% to %OUTPUT%...

pandoc "%INPUT%" -o "%OUTPUT%" ^
    --extract-media=media ^
    --wrap=none ^
    --markdown-headings=atx

if %ERRORLEVEL% EQU 0 (
    echo ✓ Successfully created %OUTPUT%
    echo Note: Images extracted to ./media folder
) else (
    echo ✗ Conversion failed
    echo Note: PDF conversion quality depends on source PDF structure
)
