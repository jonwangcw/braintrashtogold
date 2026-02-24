@echo off
setlocal
cd /d %~dp0

if not exist .venv (
  py -3 -m venv .venv
)

call .venv\Scripts\activate.bat
if errorlevel 1 goto :fail

python -m pip install --upgrade pip
if errorlevel 1 goto :fail

python -m pip install -e .
if errorlevel 1 goto :fail

if not exist .env (
  copy .env.example .env >nul
  echo Created .env from .env.example. Add API keys before using ingestion/LLM features.
)

echo Starting Retention App at http://127.0.0.1:8000
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

goto :eof

:fail
echo Failed to start Retention App.
pause
exit /b 1
