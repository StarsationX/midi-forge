@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM 7z-compress the portable bundle into multi-volume archives so each part
REM is under GitHub Releases' 2 GB-per-asset cap. Also write SHA256 checksums.

set "VER=1.0.0"
set "BUNDLE=dist\midi-forge-portable-%VER%"
set "OUT_BASE=dist\midi-forge-portable-%VER%"
set "SZ=C:\Program Files\7-Zip\7z.exe"

if not exist "%BUNDLE%" (
  echo [ERROR] Bundle missing: %BUNDLE%
  echo Run build_portable.bat first.
  exit /b 1
)
if not exist "%SZ%" (
  echo [ERROR] 7-Zip not found at "%SZ%".
  echo Install with: winget install --id 7zip.7zip
  exit /b 1
)

echo Bundle size:
"%SZ%" h -scrcSHA256 "%BUNDLE%" >nul 2>&1
for /f "tokens=*" %%i in ('powershell -NoProfile -Command "'{0:N1} GB' -f ((Get-ChildItem '%BUNDLE%' -Recurse ^| Measure-Object -Property Length -Sum).Sum / 1GB)"') do echo   %%i

echo.
echo Removing any old archive parts...
del "%OUT_BASE%.7z.*" 2>nul

echo.
echo Compressing with LZMA2 (mx=3, no solid mode, multi-volume 1900 MB per part)...
REM mx=9 + solid mode wants ~7 GB of RAM and takes hours on this bundle since
REM most of the size is already-compressed wheels. mx=3 -ms=off is much faster
REM for a few % more on-disk size.
"%SZ%" a -t7z -mx=3 -ms=off -mmt=on -v1900m "%OUT_BASE%.7z" "%BUNDLE%\*" -r
if errorlevel 1 (
  echo [ERROR] 7z compression failed.
  exit /b 1
)

echo.
echo Generating SHA256 checksums...
del "%OUT_BASE%.sha256.txt" 2>nul
for %%F in ("%OUT_BASE%.7z.*") do (
  for /f "tokens=*" %%h in ('powershell -NoProfile -Command "(Get-FileHash '%%F' -Algorithm SHA256).Hash.ToLower()"') do (
    echo %%h  %%~nxF >> "%OUT_BASE%.sha256.txt"
  )
)

echo.
echo === Archive parts ===
dir /b "%OUT_BASE%.7z.*"
echo.
echo === SHA256 checksums ===
type "%OUT_BASE%.sha256.txt"
echo.
echo Ready to upload to GitHub Releases.
endlocal
