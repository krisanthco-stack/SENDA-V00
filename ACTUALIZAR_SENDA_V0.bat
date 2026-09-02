@echo off
setlocal
cd /d "%~dp0"
title SENDA.V0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\update.ps1"
set "SENDA_RC=%ERRORLEVEL%"
if not "%SENDA_RC%"=="0" (
  echo.
  echo ERROR: La operacion no pudo completarse. Revise el mensaje anterior.
  echo.
  pause
  exit /b %SENDA_RC%
)
echo.
echo Operacion completada.
pause
exit /b 0
