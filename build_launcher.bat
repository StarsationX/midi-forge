@echo off
setlocal
cd /d "%~dp0"

REM DEPRECATED as of v1.3.0 — superseded by build_app.bat, which freezes the
REM PySide6 app itself (in-app setup page + updater) instead of a separate
REM tkinter launcher. Kept for reference only.

REM Build the self-installing MidiForge.exe launcher with PyInstaller.
REM Uses the dev venv's PyInstaller. The launcher carries the app scripts +
REM wheelhouse as bundled data ("payload"); everything heavy is fetched at
REM first run into %LOCALAPPDATA%\midi-forge.

set "VENV=C:\Users\stars\piano-midi\venv"
set "VPY=%VENV%\Scripts\python.exe"

echo Ensuring PyInstaller is installed...
"%VPY%" -m pip install --disable-pip-version-check pyinstaller 1>nul
if errorlevel 1 ( echo [ERROR] could not install pyinstaller & exit /b 1 )

echo Cleaning previous launcher build...
rmdir /s /q build 2>nul
del /q MidiForge.spec 2>nul

REM Stage payload files into a temp folder so --add-data has one clean source.
set "PAY=%TEMP%\mf_payload"
rmdir /s /q "%PAY%" 2>nul
mkdir "%PAY%"
for %%F in (app.py song_to_midi.py transcribe.py stem_to_midi.py audio_utils.py analyze.py yt_download.py download_assets.py verify_install.py requirements.txt README.md LICENSE PianoExtractor.bat SongToMidi.bat SongToMidiMax.bat Transcribe.bat StemToMidi.bat) do copy /Y "%%F" "%PAY%\" >nul
xcopy /e /i /y wheelhouse "%PAY%\wheelhouse" >nul

echo Building MidiForge.exe...
"%VPY%" -m PyInstaller --noconfirm --onefile --windowed ^
  --name MidiForge ^
  --distpath dist ^
  --workpath build ^
  --add-data "%PAY%;payload" ^
  launcher.py
if errorlevel 1 ( echo [ERROR] PyInstaller build failed & exit /b 1 )

rmdir /s /q "%PAY%" 2>nul
echo.
echo Done: dist\MidiForge.exe
endlocal
