@echo off
setlocal
if "%~1"=="" (
  echo Drag an audio file onto this .bat to transcribe it to MIDI.
  pause
  exit /b 1
)
"%~dp0venv\Scripts\python.exe" "%~dp0transcribe.py" "%~1"
pause
