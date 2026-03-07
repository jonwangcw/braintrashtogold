@echo off
schtasks /delete /tn "Rot2Gold Quiz Reminder" /f
if errorlevel 1 (
    echo Task not found or could not be removed.
) else (
    echo Notification task removed.
)
pause
