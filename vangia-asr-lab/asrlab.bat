@echo off
setlocal
set "PYTHONPATH=%~dp0src"
set "PYTHONUTF8=1"
"%~dp0.venv\Scripts\python.exe" -m asrlab %*
exit /b %errorlevel%
