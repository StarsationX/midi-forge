@echo off
if exist "%~dp0python\pythonw.exe" (
  start "" "%~dp0python\pythonw.exe" "%~dp0app.py"
) else if exist "%~dp0venv\Scripts\pythonw.exe" (
  start "" "%~dp0venv\Scripts\pythonw.exe" "%~dp0app.py"
) else (
  echo Neither portable Python nor venv found. Run install.bat first.
  pause
)
