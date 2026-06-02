@echo off
chcp 65001 >nul
title HLA — Setup

echo.
echo ================================================================
echo   Hydrogenation Literature Agent v1 — Setup
echo ================================================================
echo.

:: ── Find Python ───────────────────────────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH.
    echo   Please install Python 3.10+ from https://python.org
    echo   and ensure it is added to PATH.
    pause
    exit /b 1
)

python --version

:: ── Create virtual environment ────────────────────────────────────────────────
echo.
echo [1/4] Creating virtual environment (.venv) ...
if exist "%~dp0.venv" (
    echo   .venv already exists, skipping creation.
) else (
    python -m venv "%~dp0.venv"
    if errorlevel 1 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
)

:: ── Activate and install ──────────────────────────────────────────────────────
echo.
echo [2/4] Installing Python dependencies ...
"%~dp0.venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
"%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo [ERROR] pip install failed. Check your internet connection.
    pause
    exit /b 1
)

:: ── Install Playwright Chromium ───────────────────────────────────────────────
echo.
echo [3/4] Installing Playwright Chromium browser (for browser PDF download) ...
"%~dp0.venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 (
    echo [WARNING] Playwright Chromium install failed.
    echo   Browser-mode PDF download will use system Chrome if available.
    echo   API-mode download is unaffected.
)

:: ── Create required directories ───────────────────────────────────────────────
echo.
echo [4/4] Creating project directories ...
for %%d in (outputs outputs\logs papers\api_oa papers\manual_access data\Fe_H2 data\Co_H2 data\Mn_H2 data\Ni_H2) do (
    if not exist "%~dp0%%d" mkdir "%~dp0%%d"
)

echo.
echo ================================================================
echo   Setup complete.
echo.
echo   Quick start:
echo     run_search.bat                          (Fe H2, default)
echo     run_search.bat config\Co_H2_asymmetric_hydrogenation.yaml
echo.
echo   Full pipeline:
echo     1. run_search.bat     [config]
echo     2. run_screening.bat  [config]
echo     3. run_download.bat   [config]          (API, open access)
echo        run_download.bat   [config] browser  (institutional)
echo     4. run_extraction.bat [config]
echo.
echo   See README.md for detailed instructions.
echo ================================================================
echo.
pause
