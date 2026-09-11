@echo off
REM ============================================================
REM   IT Ticketing System - Windows client uninstaller
REM
REM   Removes the logon Scheduled Task and the HKCU Run entry so
REM   nothing tries to start the client again, stops any running
REM   copy, then optionally removes its stored data.
REM
REM   Usage:  uninstall.bat [/purge]
REM             /purge  also delete the client's saved data
REM                     (client id, settings, offline queue)
REM
REM   Runs as the logged-on user - no administrator rights needed.
REM ============================================================
setlocal

set "TASKNAME=ITTicketingClient"
set "RUNVALUE=ITTicketingClient"
set "DATA=%APPDATA%\HelpdeskClient"
set "LOCKDIR=%LOCALAPPDATA%\HelpdeskClient"

set "PURGE=0"
if /i "%~1"=="/purge" set "PURGE=1"

echo Uninstalling IT Ticketing client...

REM 1. Remove the logon scheduled task.
schtasks /Query /TN "%TASKNAME%" >nul 2>&1
if not errorlevel 1 (
    schtasks /Delete /TN "%TASKNAME%" /F >nul 2>&1
    echo   Removed logon task: %TASKNAME%
) else (
    echo   No logon task found.
)

REM 2. Remove the Run key entry (used when Task Scheduler is unavailable).
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "%RUNVALUE%" >nul 2>&1
if not errorlevel 1 (
    reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "%RUNVALUE%" /f >nul 2>&1
    echo   Removed Run key entry: %RUNVALUE%
) else (
    echo   No Run key entry found.
)

REM 3. Stop any copy still running.
taskkill /IM HelpdeskClient.exe /F >nul 2>&1
if not errorlevel 1 echo   Stopped running client.

REM 4. Optionally remove stored data.
if "%PURGE%"=="1" (
    if exist "%DATA%"    rd /s /q "%DATA%"    && echo   Removed client data: %DATA%
    if exist "%LOCKDIR%" rd /s /q "%LOCKDIR%" && echo   Removed runtime data: %LOCKDIR%
) else (
    echo   Kept client data at: %DATA%
    echo   ^(re-run with /purge to remove it^)
)

echo Done.
echo.
echo Now delete the HelpdeskClient.exe file itself if you no longer need it.
pause
