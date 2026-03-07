@echo off
setlocal

set "SCRIPTS_DIR=%~dp0"
pushd "%SCRIPTS_DIR%.."
set "APP_ROOT=%CD%"
popd

set "PYTHON=%APP_ROOT%\.venv\Scripts\python.exe"
set "NOTIFY_SCRIPT=%SCRIPTS_DIR%notify_check.py"
set "TASK_NAME=Rot2Gold Quiz Reminder"

if not exist "%PYTHON%" (
    echo ERROR: venv Python not found at: %PYTHON%
    echo Run Run_Retention_App.bat first to create the virtual environment.
    pause
    exit /b 1
)

schtasks /delete /tn "%TASK_NAME%" /f 2>nul

schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%PYTHON%\" \"%NOTIFY_SCRIPT%\"" ^
  /sc MINUTE /mo 30 ^
  /it ^
  /f

if errorlevel 1 (
    echo Failed to register scheduled task.
    pause
    exit /b 1
)

echo.
echo Registered: "%TASK_NAME%"
echo Fires every 30 minutes when you are logged in and a quiz is due.
echo To remove: run remove_notify_task.bat
pause
