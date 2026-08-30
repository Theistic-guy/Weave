@echo off
setlocal enabledelayedexpansion

echo =======================================================
echo          Weave - Nuitka Standalone Build Script
echo =======================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not found on PATH. Please install Python 3.10+ and add it to PATH.
    pause
    exit /b 1
)

:: Check Nuitka
python -m nuitka --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] Nuitka not found. Installing requirements...
    pip install -r requirements.txt
)

echo Select Build Type:
echo [1] Standalone Folder (Recommended - Fast startup, easy debugging)
echo [2] Single-File .EXE (Portable - Self-contained single file)
echo.
set /p BUILD_CHOICE="Enter choice [1 or 2] (Default=1): "
if "%BUILD_CHOICE%"=="" set BUILD_CHOICE=1

echo.
echo Compiling Weave with Nuitka... Please wait, this may take a few minutes.
echo.

if "%BUILD_CHOICE%"=="2" (
    python -m nuitka ^
        --onefile ^
        --enable-plugin=pyqt5 ^
        --windows-disable-console ^
        --windows-icon-from-ico=logo.ico ^
        --include-data-file=logo.ico=logo.ico ^
        --output-filename=Weave.exe ^
        --output-dir=dist ^
        --assume-yes-for-downloads ^
        main.py
) else (
    python -m nuitka ^
        --standalone ^
        --enable-plugin=pyqt5 ^
        --windows-disable-console ^
        --windows-icon-from-ico=logo.ico ^
        --include-data-file=logo.ico=logo.ico ^
        --output-filename=Weave.exe ^
        --output-dir=dist ^
        --assume-yes-for-downloads ^
        main.py
)

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. Check the error log above.
    pause
    exit /b 1
)

echo.
echo =======================================================
echo [SUCCESS] Build completed! Output is in the 'dist' directory.
echo =======================================================
pause
