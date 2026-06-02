@echo off
chcp 65001 >nul
title HLA — Stage 2: Title/Abstract Screening

if exist "%~dp0.venv\Scripts\python.exe" (
    set PYTHON=%~dp0.venv\Scripts\python.exe
) else (
    set PYTHON=python
)

if "%1"=="" (
    set CONFIG=config\Fe_H2_asymmetric_hydrogenation.yaml
    echo [INFO] No config specified. Using default: %CONFIG%
) else (
    set CONFIG=%1
)

echo.
echo ================================================================
echo   Hydrogenation Literature Agent — Stage 2: Screening
echo   Config : %CONFIG%
echo ================================================================
echo.

cd /d "%~dp0"
"%PYTHON%" -m modules.title_abstract_screening --config "%CONFIG%"
if errorlevel 1 (
    echo.
    echo [ERROR] Stage 2 failed. Check the output above for details.
    pause
    exit /b 1
)

echo.
echo Stage 2 complete. Check outputs\ for screened Excel files.
echo Next step: run_download.bat %CONFIG%
pause
