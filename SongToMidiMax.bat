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
"%PY%" "%~dp0song_to_midi.py" "%~1"
pause
