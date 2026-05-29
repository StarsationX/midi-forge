@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo  midi-forge installer
echo ============================================================
echo.
echo This will:
echo   1. Find a Python 3.10 - 3.13 install
echo   2. Create a local venv ^(.\venv\^)
echo   3. Install PyTorch 2.11 + CUDA 12.8 ^(~3 GB^)
echo   4. Install the other Python packages
echo   5. Clone MSST
echo   6. Download BS-Rofo model + FFmpeg DLLs ^(~900 MB^)
echo   7. Verify the install
echo.
echo Needs ~10 GB free disk. ~10 minutes on a good connection.
echo Safe to re-run if anything fails - everything resumes / skips done work.
echo.

REM ---- 1. Python check (any of 3.10 - 3.13) ----
set "PYEXE="
for %%V in (3.13 3.12 3.11 3.10) do (
  if "!PYEXE!"=="" (
    py -%%V --version >nul 2>&1
    if not errorlevel 1 set "PYEXE=py -%%V"
  )
)
if "!PYEXE!"=="" (
  python --version 2>nul | findstr /R "^Python 3\.1[0123]" >nul
  if not errorlevel 1 set "PYEXE=python"
)
if "!PYEXE!"=="" (
  echo [ERROR] No suitable Python found. midi-forge needs Python 3.10 - 3.13.
  echo.
  echo Install one of:
  echo   - https://www.python.org/downloads/   ^(pick 3.12, tick "Add Python to PATH"^)
  echo   - winget install --id Python.Python.3.12
  echo Then close this window and re-run install.bat.
  pause
  exit /b 1
)

echo [1/7] Found Python: !PYEXE!
!PYEXE! --version

REM ---- 2. venv (probe; rebuild if broken) ----
set "VENV_OK="
if exist "venv\Scripts\python.exe" (
  venv\Scripts\python.exe -c "import sys, venv" >nul 2>&1
  if not errorlevel 1 set "VENV_OK=1"
)
if not defined VENV_OK (
  if exist "venv" (
    echo [2/7] Removing broken/partial venv...
    rmdir /s /q venv 2>nul
    if exist "venv" (
      echo [ERROR] Could not delete .\venv\ - close any program using it ^(e.g. PianoExtractor^) and re-run.
      pause
      exit /b 1
    )
  )
  echo [2/7] Creating virtual environment...
  !PYEXE! -m venv venv
  if errorlevel 1 (
    echo [ERROR] venv creation failed. The selected Python may be corrupt.
    echo Try installing 3.12 from https://www.python.org/downloads/ and re-run.
    pause
    exit /b 1
  )
) else (
  echo [2/7] venv already exists and works, reusing.
)

set "VPY=%~dp0venv\Scripts\python.exe"
set "PIPFLAGS=--retries 5 --timeout 60 --disable-pip-version-check"

REM Use `python -m pip` everywhere: pip.exe can't upgrade itself on Windows
REM (the running .exe is locked), which is why a direct pip.exe upgrade fails.
echo       Upgrading pip / wheel / setuptools...
"%VPY%" -m pip install %PIPFLAGS% --upgrade pip wheel setuptools 1>nul
if errorlevel 1 (
  echo [ERROR] Could not upgrade pip ^(check internet, then re-run^).
  pause
  exit /b 1
)

REM ---- 3. PyTorch (CUDA 12.8) ----
echo.
echo [3/7] Installing PyTorch 2.11 + CUDA 12.8 ^(~3 GB, takes a few minutes^)...
"%VPY%" -m pip install %PIPFLAGS% --index-url https://download.pytorch.org/whl/cu128 ^
  torch==2.11.0 torchaudio==2.11.0 torchvision==0.26.0
if errorlevel 1 (
  echo [ERROR] PyTorch install failed.
  echo Re-run install.bat - pip caches partial downloads so it will pick up where it stopped.
  pause
  exit /b 1
)
REM torchcodec ships Windows wheels only on default PyPI, not the cu128 index.
"%VPY%" -m pip install %PIPFLAGS% torchcodec==0.11.1
if errorlevel 1 (
  echo [ERROR] torchcodec install failed. Re-run install.bat.
  pause
  exit /b 1
)

REM ---- 4. Other Python deps ----
echo.
echo [4/7] Installing other Python packages...
"%VPY%" -m pip install %PIPFLAGS% -r requirements.txt
if errorlevel 1 (
  echo [ERROR] pip install -r requirements.txt failed. Re-run install.bat.
  pause
  exit /b 1
)

REM basic-pitch has a numpy build issue on 3.13 - skip its declared deps (we already have them)
"%VPY%" -m pip install %PIPFLAGS% --no-deps basic-pitch==0.4.0
if errorlevel 1 (
  echo [ERROR] basic-pitch install failed.
  pause
  exit /b 1
)
"%VPY%" -m pip install %PIPFLAGS% onnxruntime
if errorlevel 1 (
  echo [ERROR] onnxruntime install failed.
  pause
  exit /b 1
)

REM ---- 5. MSST source ----
if not exist "msst\inference.py" (
  echo.
  echo [5/7] Cloning MSST framework...
  where git >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] git is not installed. Install from https://git-scm.com/ then re-run.
    pause
    exit /b 1
  )
  if exist "msst" rmdir /s /q msst 2>nul
  git clone --depth 1 https://github.com/ZFTurbo/Music-Source-Separation-Training.git msst
  if errorlevel 1 (
    echo [ERROR] MSST clone failed.
    echo Likely causes: no internet, github.com blocked ^(try a VPN^), antivirus interference.
    pause
    exit /b 1
  )
) else (
  echo [5/7] MSST already present, skipping.
)

REM ---- 6. Model + FFmpeg downloads ----
echo.
echo [6/7] Downloading BS-Rofo-SW-Fixed model and FFmpeg DLLs ^(~900 MB^)...
"%VPY%" download_assets.py
if errorlevel 1 (
  echo [ERROR] asset download failed. Re-run install.bat - downloads resume from where they stopped.
  pause
  exit /b 1
)

REM ---- 7. Verify install ----
echo.
echo [7/7] Verifying install...
"%VPY%" verify_install.py
set "VERIFY_RC=!errorlevel!"

echo.
echo ============================================================
if "!VERIFY_RC!"=="0" (
  echo  Install complete!
) else (
  echo  Install finished with warnings - see messages above.
)
echo ============================================================
echo.
echo  Launch the GUI:    double-click PianoExtractor.bat
echo  Drag-and-drop:     drop a song onto SongToMidi.bat
echo  CLI piano stem:    drop onto Transcribe.bat
echo  CLI any stem:      drop onto StemToMidi.bat
echo.
pause
exit /b !VERIFY_RC!
