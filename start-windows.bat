@echo off
title Morph
cd /d "%~dp0"

rem ---- Find Python -------------------------------------------------------
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY goto nopython

rem ---- First run: make a private Python environment and install packages --
if not exist ".venv\Scripts\python.exe" (
  echo.
  echo   Setting up Morph for the first time. This takes a few minutes...
  echo.
  %PY% -m venv .venv || goto nopython
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto failed
)

rem ---- Keep the YouTube downloader fresh (sites change often) -------------
echo   Checking for YouTube downloader updates...
".venv\Scripts\python.exe" -m pip install -q --upgrade "yt-dlp[default]" >nul 2>nul

rem ---- Start ----------------------------------------------------------------
".venv\Scripts\python.exe" app.py
pause
exit /b

:nopython
echo.
echo   Python isn't installed (or isn't on PATH).
echo   1. Go to https://www.python.org/downloads/ and install Python 3.12 or newer.
echo   2. On the first installer screen, tick "Add python.exe to PATH".
echo   3. Double-click start-windows.bat again.
echo.
pause
exit /b

:failed
echo.
echo   Installing the packages didn't finish. Check your internet connection,
echo   then double-click start-windows.bat again.
echo.
rmdir /s /q .venv
pause
exit /b
