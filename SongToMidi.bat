@echo off
setlocal
if "%~1"=="" (
  echo Drag a song onto this .bat to get a MIDI of its piano part.
  pause
  exit /b 1
)
"%~dp0venv\Scripts\python.exe" "%~dp0song_to_midi.py" "%~1"
pause
