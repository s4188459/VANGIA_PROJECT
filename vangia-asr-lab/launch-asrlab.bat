@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python environment missing. Run setup-windows.ps1 first.
  pause
  exit /b 1
)
set "PYTHONPATH=%~dp0src"
set "PYTHONUTF8=1"
".venv\Scripts\python.exe" -m asrlab ui --run-dir runs\historical
if errorlevel 1 pause
