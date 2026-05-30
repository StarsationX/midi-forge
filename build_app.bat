@echo off
setlocal
cd /d "%~dp0"

REM Build the all-in-one MidiForge.exe: app.py frozen WITH PySide6 bundled, so
REM the GUI shows instantly. Pipeline scripts + wheelhouse ride along as data
REM and are extracted to %LOCALAPPDATA%\midi-forge; the heavy env (torch/model)
REM is downloaded by the in-app setup page on first run.

set "VENV=C:\Users\stars\piano-midi\venv"
set "VPY=%VENV%\Scripts\python.exe"

echo Ensuring PyInstaller is installed...
"%VPY%" -m pip install --disable-pip-version-check pyinstaller 1>nul
if errorlevel 1 ( echo [ERROR] could not install pyinstaller & exit /b 1 )

echo Cleaning previous build...
rmdir /s /q build 2>nul
del /q MidiForge.spec 2>nul

REM Stage the payload (pipeline scripts + wheelhouse) for --add-data.
set "PAY=%TEMP%\mf_payload"
rmdir /s /q "%PAY%" 2>nul
mkdir "%PAY%"
for %%F in (app.py song_to_midi.py transcribe.py stem_to_midi.py audio_utils.py analyze.py yt_download.py download_assets.py verify_install.py requirements.txt README.md LICENSE) do copy /Y "%%F" "%PAY%\" >nul
xcopy /e /i /y wheelhouse "%PAY%\wheelhouse" >nul

echo Building MidiForge.exe (bundling PySide6, takes a few minutes)...
"%VPY%" -m PyInstaller --noconfirm --onefile --windowed ^
  --name MidiForge ^
  --distpath dist ^
  --workpath build ^
  --add-data "%PAY%;payload" ^
  --exclude-module torch --exclude-module numpy --exclude-module scipy ^
  --exclude-module matplotlib --exclude-module pandas ^
  app.py
if errorlevel 1 ( echo [ERROR] PyInstaller build failed & exit /b 1 )

rmdir /s /q "%PAY%" 2>nul
echo.
echo Done: dist\MidiForge.exe
endlocal
