@echo off
chcp 65001 >nul
title HLA — Stage 1: Literature Search

:: ── Python interpreter ────────────────────────────────────────────────────────
:: Priority: project venv > system python
if exist "%~dp0.venv\Scripts\python.exe" (
    set PYTHON=%~dp0.venv\Scripts\python.exe
) else (
    set PYTHON=python
)

:: ── Config selection ──────────────────────────────────────────────────────────
if "%1"=="" (
    set CONFIG=config\Fe_H2_asymmetric_hydrogenation.yaml
    echo [INFO] No config specified. Using default: %CONFIG%
    echo        Usage: run_search.bat config\Co_H2_asymmetric_hydrogenation.yaml
) else (
    set CONFIG=%1
)

:: ── Optional overrides ────────────────────────────────────────────────────────
set PER_QUERY=
set MAX_REVIEWS=
set MAX_PRIMARY=
if not "%2"=="" set PER_QUERY=--per-query %2
if not "%3"=="" set MAX_REVIEWS=--max-reviews %3
if not "%4"=="" set MAX_PRIMARY=--max-primary %4

echo.
echo ================================================================
echo   Hydrogenation Literature Agent — Stage 1: Literature Search
echo   Config : %CONFIG%
echo ================================================================
echo.

cd /d "%~dp0"
"%PYTHON%" -m modules.literature_search --config "%CONFIG%" %PER_QUERY% %MAX_REVIEWS% %MAX_PRIMARY%

echo.
echo Stage 1 complete. Check outputs\ for results.
echo Next step: run_screening.bat %CONFIG%
pause
