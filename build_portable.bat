@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM Build a portable midi-forge bundle: embeddable Python + pip-installed deps
REM + bundled models/ffmpeg/msst + scripts. Output: dist\midi-forge-portable-VER\

set "VER=1.0.0"
set "PYVER=3.13.5"
set "BUNDLE=dist\midi-forge-portable-%VER%"
set "PYEMBED_URL=https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-embed-amd64.zip"
set "GETPIP_URL=https://bootstrap.pypa.io/get-pip.py"

echo ============================================================
echo  midi-forge portable bundle builder  (v%VER%, py %PYVER%)
echo ============================================================
echo Output: %BUNDLE%
echo.

REM ---- 0-2. Set up embedded Python (idempotent via goto to dodge batch nesting bugs) ----
if exist "%BUNDLE%\python\python.exe" (
  echo [0-2/9] Reusing existing bundle Python at %BUNDLE%\python
  goto :pip_bootstrap
)

if exist "%BUNDLE%" (
  echo [0/9] Removing broken partial bundle...
  rmdir /s /q "%BUNDLE%"
)
mkdir "%BUNDLE%\python"

echo [1/9] Downloading Python %PYVER% embeddable distribution...
curl --fail -L -o "%BUNDLE%\python-embed.zip" "%PYEMBED_URL%"
if errorlevel 1 ( echo [ERROR] embeddable Python download failed & exit /b 1 )
tar -xf "%BUNDLE%\python-embed.zip" -C "%BUNDLE%\python"
if errorlevel 1 ( echo [ERROR] extracting embeddable Python failed & exit /b 1 )
del "%BUNDLE%\python-embed.zip"

echo [2/9] Configuring embedded Python (enable site-packages)...
for %%F in ("%BUNDLE%\python\python*._pth") do (
  powershell -NoProfile -Command "(Get-Content '%%F') -replace '#import site', 'import site' | Set-Content '%%F'"
)

:pip_bootstrap

REM ---- 3. Bootstrap pip (skip if already installed) ----
if not exist "%BUNDLE%\python\Scripts\pip.exe" (
  echo [3/9] Bootstrapping pip...
  curl --fail -L -o "%BUNDLE%\python\get-pip.py" "%GETPIP_URL%"
  if errorlevel 1 ( echo [ERROR] get-pip.py download failed & exit /b 1 )
  "%BUNDLE%\python\python.exe" "%BUNDLE%\python\get-pip.py" --no-warn-script-location
  if errorlevel 1 ( echo [ERROR] pip bootstrap failed & exit /b 1 )
  del "%BUNDLE%\python\get-pip.py"
) else (
  echo [3/9] pip already installed, skipping.
)

set "BPY=%BUNDLE%\python\python.exe"
set "PIPFLAGS=--retries 5 --timeout 60 --disable-pip-version-check --no-warn-script-location --find-links wheelhouse"

REM ---- 4. PyTorch (CUDA 12.8) ----
echo [4/9] Installing PyTorch 2.11 + CUDA 12.8 (~3 GB, several minutes)...
"%BPY%" -m pip install %PIPFLAGS% --index-url https://download.pytorch.org/whl/cu128 ^
  torch==2.11.0 torchaudio==2.11.0 torchvision==0.26.0
if errorlevel 1 ( echo [ERROR] PyTorch install failed & exit /b 1 )
"%BPY%" -m pip install %PIPFLAGS% torchcodec==0.11.1
if errorlevel 1 ( echo [ERROR] torchcodec install failed & exit /b 1 )

REM ---- 5. Other deps ----
echo [5/9] Installing other Python packages...
"%BPY%" -m pip install %PIPFLAGS% -r requirements.txt
if errorlevel 1 ( echo [ERROR] requirements install failed & exit /b 1 )
"%BPY%" -m pip install %PIPFLAGS% --no-deps basic-pitch==0.4.0
if errorlevel 1 ( echo [ERROR] basic-pitch install failed & exit /b 1 )
"%BPY%" -m pip install %PIPFLAGS% onnxruntime
if errorlevel 1 ( echo [ERROR] onnxruntime install failed & exit /b 1 )

REM ---- 6. MSST ----
echo [6/9] Cloning MSST...
git clone --depth 1 https://github.com/ZFTurbo/Music-Source-Separation-Training.git "%BUNDLE%\msst"
if errorlevel 1 ( echo [ERROR] MSST clone failed & exit /b 1 )
rmdir /s /q "%BUNDLE%\msst\.git" 2>nul

REM ---- 7. Model + FFmpeg ----
echo [7/9] Downloading BS-Rofo model and FFmpeg DLLs into bundle...
copy /Y download_assets.py "%BUNDLE%\" >nul
"%BPY%" "%BUNDLE%\download_assets.py"
if errorlevel 1 ( echo [ERROR] asset download failed & exit /b 1 )

REM ---- 8. Scripts ----
echo [8/9] Copying scripts...
copy /Y *.py "%BUNDLE%\" >nul
copy /Y PianoExtractor.bat "%BUNDLE%\" >nul
copy /Y SongToMidi.bat "%BUNDLE%\" >nul
copy /Y SongToMidiMax.bat "%BUNDLE%\" >nul
copy /Y Transcribe.bat "%BUNDLE%\" >nul
copy /Y StemToMidi.bat "%BUNDLE%\" >nul
copy /Y README.md "%BUNDLE%\" >nul
copy /Y LICENSE "%BUNDLE%\" >nul
copy /Y requirements.txt "%BUNDLE%\" >nul
REM Build-only scripts don't go in the bundle:
del "%BUNDLE%\install.bat" 2>nul
del "%BUNDLE%\midi-forge.iss" 2>nul

REM ---- 9. Verify ----
echo [9/9] Running smoke test inside the bundle...
"%BPY%" "%BUNDLE%\verify_install.py"
if errorlevel 1 (
  echo [WARN] verify_install.py reported issues - check above
) else (
  echo [OK] bundle verified
)

echo.
echo ============================================================
echo  Bundle built. Inspect: %BUNDLE%
echo  Next: zip / 7z it and attach to a GitHub release.
echo ============================================================
endlocal
