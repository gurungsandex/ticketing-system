@echo off
setlocal enabledelayedexpansion
cls

echo.
echo  ============================================================
echo    Medical Offices of Manhattan  ^|  IT Helpdesk v4.0
echo    Windows Setup Script
echo  ============================================================
echo.

REM ── 1. Python check ──────────────────────────────────
echo  [1/5] Checking Python...
python --version >nul 2>&1
if ERRORLEVEL 1 (
    echo.
    echo  ERROR: Python not found.
    echo.
    echo  Fix:
    echo    1. Download Python 3.10+ from https://python.org/downloads
    echo    2. During install, check "Add Python to PATH"
    echo    3. Reboot, then run this file again.
    echo.
    pause & exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo  OK: %%v
echo.

REM ── 2. Locate paths ──────────────────────────────────
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "BACKEND=%ROOT%\backend"
set "LOGS=%ROOT%\logs"

if not exist "%BACKEND%\main.py" (
    echo  ERROR: backend\main.py not found.
    echo  Make sure setup.bat is in the helpdeskv05\ root folder.
    pause & exit /b 1
)

if not exist "%LOGS%" mkdir "%LOGS%"

REM ── 3. Install dependencies ──────────────────────────
echo  [2/5] Installing dependencies (first run may take ~30 seconds)...
cd /d "%BACKEND%"
python -m pip install --upgrade pip --quiet 2>nul
python -m pip install -r requirements.txt --quiet
if ERRORLEVEL 1 (
    echo.
    echo  ERROR: pip install failed. Run this manually to see the error:
    echo    cd "%BACKEND%"
    echo    python -m pip install -r requirements.txt
    echo.
    pause & exit /b 1
)
echo  OK: Dependencies installed.
echo.

REM ── 4. Detect LAN IP ─────────────────────────────────
echo  [3/5] Detecting server IP...
set "LAN_IP=YOUR_SERVER_IP"
for /f "tokens=2 delims=:" %%a in (
    'ipconfig ^| findstr /i "IPv4" ^| findstr /v "127.0.0.1" ^| findstr /v "172." ^| findstr /v "169.254"'
) do (
    for /f "tokens=1" %%b in ("%%a") do (
        set "LAN_IP=%%b"
        goto :ip_done
    )
)
:ip_done
echo  IP: %LAN_IP%
echo.

REM ── 5. Stop any existing server ──────────────────────
echo  [4/5] Stopping any running server on port 8000...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /PID %%p /F >nul 2>&1
)
timeout /t 1 /nobreak >nul
echo  OK.
echo.

REM ── 6. Write daemon + launch in background ───────────
echo  [5/5] Launching server in background...

set "DAEMON=%ROOT%\mom_server_daemon.pyw"
set "LOG=%LOGS%\server.log"

REM Write the daemon Python script.
REM .pyw = no console window. creationflags=0x08000000 keeps uvicorn windowless too.
(
echo import subprocess
echo import sys
echo import time
echo.
echo BACKEND          = r"%BACKEND%"
echo LOG              = r"%LOG%"
echo CREATE_NO_WINDOW = 0x08000000
echo.
echo while True:
echo     with open^(LOG, "a"^) as lf:
echo         p = subprocess.Popen^(
echo             [sys.executable, "-m", "uvicorn", "main:app",
echo              "--host", "0.0.0.0", "--port", "8000"],
echo             cwd=BACKEND, stdout=lf, stderr=lf,
echo             creationflags=CREATE_NO_WINDOW,
echo         ^)
echo         p.wait^(^)
echo     time.sleep^(3^)
) > "%DAEMON%"

REM Find pythonw.exe — always sits next to python.exe
set "PYTHONW="
for /f "tokens=*" %%p in ('where python 2^>nul') do (
    set "PYTHONW=%%~dppythonw.exe"
    goto :found_pw
)
:found_pw
if not exist "%PYTHONW%" (
    REM Unlikely fallback: use plain python (window will flash briefly then hide)
    for /f "tokens=*" %%p in ('where python 2^>nul') do set "PYTHONW=%%p"
)

REM Write stop_server.bat
(
echo @echo off
echo echo Stopping MOM IT Helpdesk server...
echo for /f "tokens=5" %%%%p in ^('netstat -ano 2^^^>nul ^| findstr ":8000 " ^| findstr "LISTENING"'^) do taskkill /PID %%%%p /F ^>nul 2^^^>^^^&1
echo taskkill /im pythonw.exe /F ^>nul 2^^^>^^^&1
echo echo.
echo echo Done. Server stopped.
echo pause
) > "%ROOT%\stop_server.bat"

REM Launch: start without /b so pythonw gets its own independent process group
start "" "%PYTHONW%" "%DAEMON%"

REM Brief wait so uvicorn has time to bind the port
timeout /t 3 /nobreak >nul

echo.
echo  ============================================================
echo    Server running in BACKGROUND
echo    Safe to close this window — server keeps running.
echo.
echo    Admin Panel  ^|  http://%LAN_IP%:8000/admin
echo    Tech Panel   ^|  http://%LAN_IP%:8000/tech
echo    Health Check ^|  http://%LAN_IP%:8000/health
echo.
echo    Default login:  admin / admin123
echo    Change password on first login.
echo.
echo    Client config:  SERVER_URL = "http://%LAN_IP%:8000"
echo.
echo    Logs:           logs\server.log
echo    Stop server:    stop_server.bat
echo    Restart server: run setup.bat again
echo  ============================================================
echo.
pause
