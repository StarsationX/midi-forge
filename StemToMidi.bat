@echo off
setlocal
if "%~1"=="" (
  echo Drag any audio stem (vocals, guitar, synth, etc.) onto this .bat to convert to MIDI.
  echo Uses basic-pitch - works on most instruments. For piano specifically, use Transcribe.bat instead.
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
"%PY%" "%~dp0stem_to_midi.py" "%~1"
pause
