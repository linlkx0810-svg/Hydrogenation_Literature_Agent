@echo off
chcp 65001 >nul
title HLA — Stages 4+5: Fulltext Screening + Data Extraction

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
echo   Stage 4: Full-text PDF Screening
echo   Config : %CONFIG%
echo ================================================================
echo.

cd /d "%~dp0"
"%PYTHON%" -m modules.fulltext_screening --config "%CONFIG%"

echo.
echo ================================================================
echo   Stage 5: Reaction Data Extraction
echo ================================================================
echo.

"%PYTHON%" -m modules.reaction_data_extraction --config "%CONFIG%"

echo.
echo Stages 4+5 complete. Check outputs\ for results.
pause
