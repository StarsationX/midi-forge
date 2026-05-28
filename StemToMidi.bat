@echo off
setlocal
if "%~1"=="" (
  echo Drag any audio stem (vocals, guitar, synth, etc.) onto this .bat to convert to MIDI.
  echo Uses basic-pitch - works on most instruments. For piano specifically, use Transcribe.bat instead.
  pause
  exit /b 1
)
"%~dp0venv\Scripts\python.exe" "%~dp0stem_to_midi.py" "%~1"
pause
