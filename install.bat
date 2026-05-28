@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo  midi-forge installer
echo ============================================================
echo.

REM ---- 1. Python check ----
where py >nul 2>&1
if errorlevel 1 (
  where python >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] Python is not installed.
    echo Install Python 3.13 from https://www.python.org/downloads/  ^(check "Add to PATH"^)
    pause
    exit /b 1
  )
  set "PYEXE=python"
) else (
  set "PYEXE=py -3.13"
)

echo [1/6] Found Python: %PYEXE%
%PYEXE% --version

REM ---- 2. venv ----
if not exist "venv\Scripts\python.exe" (
  echo [2/6] Creating virtual environment...
  %PYEXE% -m venv venv
  if errorlevel 1 ( echo venv creation failed & pause & exit /b 1 )
) else (
  echo [2/6] venv already exists, reusing.
)

set "VPY=%~dp0venv\Scripts\python.exe"
set "VPIP=%~dp0venv\Scripts\pip.exe"

"%VPIP%" install --upgrade pip wheel setuptools >nul

REM ---- 3. PyTorch (CUDA 12.8) ----
echo [3/6] Installing PyTorch 2.11 + CUDA 12.8 (~3GB, takes a few minutes)...
"%VPIP%" install --index-url https://download.pytorch.org/whl/cu128 ^
  torch==2.11.0 torchaudio==2.11.0 torchvision==0.26.0 torchcodec==0.11.1
if errorlevel 1 ( echo torch install failed & pause & exit /b 1 )

REM ---- 4. Other Python deps ----
echo [4/6] Installing other Python packages...
"%VPIP%" install -r requirements.txt
if errorlevel 1 ( echo pip install failed & pause & exit /b 1 )

REM basic-pitch has a build issue on Python 3.13 numpy - install without its deps
"%VPIP%" install --no-deps basic-pitch==0.4.0
"%VPIP%" install onnxruntime

REM ---- 5. MSST source ----
if not exist "msst\inference.py" (
  echo [5/6] Cloning MSST framework...
  where git >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] git is not installed. Install from https://git-scm.com/
    pause
    exit /b 1
  )
  git clone --depth 1 https://github.com/ZFTurbo/Music-Source-Separation-Training.git msst
  if errorlevel 1 ( echo MSST clone failed & pause & exit /b 1 )
) else (
  echo [5/6] MSST already present, skipping.
)

REM ---- 6. Model + FFmpeg downloads ----
echo [6/6] Downloading BS-Rofo-SW-Fixed model and FFmpeg DLLs (~900MB)...
"%VPY%" download_assets.py
if errorlevel 1 ( echo asset download failed & pause & exit /b 1 )

echo.
echo ============================================================
echo  Verifying CUDA...
echo ============================================================
"%VPY%" -c "import torch; ok = torch.cuda.is_available(); print('CUDA available:', ok); print('GPU:', torch.cuda.get_device_name(0) if ok else 'CPU only - things will be very slow')"

echo.
echo ============================================================
echo  Install complete!
echo  Double-click PianoExtractor.bat to launch the GUI,
echo  or drag a song onto SongToMidi.bat.
echo ============================================================
pause
