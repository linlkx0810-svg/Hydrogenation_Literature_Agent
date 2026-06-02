@echo off
chcp 65001 >nul
title HLA — Stage 3: PDF Download

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

:: Mode: api (default, automated) or browser (institutional, interactive)
if "%2"=="browser" (
    set MODE=browser
    set ROW_ARG=
    if not "%3"=="" set ROW_ARG=--row %3
    echo.
    echo ================================================================
    echo   Stage 3: PDF Download — BROWSER MODE (institutional access)
    echo   Config : %CONFIG%
    echo   A visible Chrome window will open.
    echo   Complete any login / challenge manually when prompted.
    echo ================================================================
    echo.
    cd /d "%~dp0"
    "%PYTHON%" -m modules.pdf_download --config "%CONFIG%" --mode browser %ROW_ARG%
    if errorlevel 1 (
        echo.
        echo [ERROR] Stage 3 (browser mode) failed. Check the output above for details.
        pause
        exit /b 1
    )
) else (
    echo.
    echo ================================================================
    echo   Stage 3: PDF Download — API MODE (open access only)
    echo   Config : %CONFIG%
    echo   For institutional access, run: run_download.bat %CONFIG% browser
    echo ================================================================
    echo.
    cd /d "%~dp0"
    "%PYTHON%" -m modules.pdf_download --config "%CONFIG%" --mode api
    if errorlevel 1 (
        echo.
        echo [ERROR] Stage 3 (API mode) failed. Check the output above for details.
        pause
        exit /b 1
    )
)

echo.
echo Stage 3 complete. Check papers\ for downloaded PDFs.
echo Next step: run_extraction.bat %CONFIG%
pause
