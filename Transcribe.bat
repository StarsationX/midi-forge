@echo off
setlocal
if "%~1"=="" (
  echo Drag an audio file onto this .bat to transcribe it to MIDI.
  pause
  exit /b 1
)
if exist "%~dp0python\python.exe" (
  set "PY=%~dp0python\python.exe"
) else if exist "%~dp0venv\Scripts\python.exe" (
  set "PY=%~dp0venv\Scripts\python.exe"
) else (
  echo Neither portable Python nor venv found. Run install.bat first.
  pause
  exit /b 1
)
set PYTHONNOUSERSITE=1
"%PY%" "%~dp0transcribe.py" "%~1"
pause
