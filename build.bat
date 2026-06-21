@echo off
setlocal enabledelayedexpansion

:: ================================================================
::  taowuDB Build Script
::  默认分体式打包 (onedir):
::    - Python 代码 & 运行库 -> _internal/
::    - 外部资源 -> EXE 同级目录
:: ================================================================

title taowuDB Build

:: ── Locate project root ───────────────────────────────────────
set "PROJ_ROOT=%~dp0"
cd /d "%PROJ_ROOT%"

:: ── Check Python ──────────────────────────────────────────────
echo [Check] Looking for Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found! Please install Python 3.10+
    echo         Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo         Python %%v [OK]

:: ── Check/Install PyInstaller ─────────────────────────────────
echo [Check] Looking for PyInstaller...
python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo [Install] PyInstaller not found, installing...
    pip install pyinstaller -q
    if %errorlevel% neq 0 (
        echo [ERROR] PyInstaller install failed!
        pause
        exit /b 1
    )
    echo         PyInstaller installed [OK]
) else (
    echo         PyInstaller found [OK]
)

:: ── Check key dependencies ────────────────────────────────────
echo [Check] Looking for key dependencies...
for %%p in (PySide6 pyqtgraph Pygments zhconv pymysql) do (
    python -c "import %%p" >nul 2>&1
    if !errorlevel! neq 0 (
        echo [Install] %%p not found, installing...
        pip install %%p -q
    )
)
echo         All dependencies ready [OK]

:: ── Detect command-line arguments ─────────────────────────────
::   --onefile  单文件打包 (传统模式)
::   --fast     快速打包 (跳过 UPX)
::   --help     查看帮助
set BUILD_ARGS=--fast
:parse_args
if "%~1"=="" goto run_build
if /i "%~1"=="--onefile" (
    set BUILD_ARGS=%BUILD_ARGS% --onefile
    shift
    goto parse_args
)
if /i "%~1"=="--fast" (
    :: already default
    shift
    goto parse_args
)
if /i "%~1"=="--help" (
    goto show_help
)
shift
goto parse_args

:show_help
echo.
echo   Usage: build.bat [options]
echo.
echo   Options:
echo     --onefile    Single-file EXE mode (legacy)
echo     --fast       Skip UPX compression (default)
echo     --help       Show this help
echo.
echo   Default: onedir mode (split packaging)
echo     - Python code + libs in _internal/
echo     - External resources alongside EXE
echo.
pause
exit /b 0

:: ── Run Python build script ───────────────────────────────────
:run_build
echo.
echo ================================================================
echo   Starting build...
echo   Mode: onedir (split packaging) [default]
echo   Extra flags: %BUILD_ARGS%
echo ================================================================
echo.

python "%PROJ_ROOT%build_taowudb.py" %BUILD_ARGS%
set BUILD_RESULT=%errorlevel%

if %BUILD_RESULT% neq 0 (
    echo.
    echo   [FAILED] Build failed!
    echo.
    pause
    exit /b 1
)

echo.
echo   [SUCCESS] Build completed!
echo   Output: %PROJ_ROOT%dist\taowuDB\
echo   Main exe: taowuDB.exe
echo.
echo   Directory structure:
echo     taowuDB\               ^<- distribute this folder
echo     +-- taowuDB.exe        Main program
echo     +-- _internal\         Python code + runtime libs
echo     +-- taowu_data\        Database files (auto-created)
echo     +-- xuanwu_firewall\   Firewall data
echo     +-- config_gui\        GUI resources
echo     +-- Readme.txt         Usage guide
echo.

pause
endlocal
