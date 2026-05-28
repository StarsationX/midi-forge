@echo off
setlocal
if "%~1"=="" (
  echo Drag a song onto this .bat for maximum-quality piano MIDI.
  echo Uses TTA + bigshifts=3 + fine segment hop - ~6x slower but cleaner.
  pause
  exit /b 1
)
set USE_TTA=1
set BIGSHIFTS=3
set SEGMENT_HOP=2
"%~dp0venv\Scripts\python.exe" "%~dp0song_to_midi.py" "%~1"
pause
