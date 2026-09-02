@echo off
setlocal
cd /d "%~dp0"
title SENDA.V0

set "SENDA_PY="
where py >nul 2>&1
if not errorlevel 1 set "SENDA_PY=py -3"
if not defined SENDA_PY (
  where python >nul 2>&1
  if not errorlevel 1 set "SENDA_PY=python"
)

if not defined SENDA_PY (
  echo.
  echo ERROR: No se encontro Python 3.
  echo Instale Python 3 y vuelva a ejecutar SENDA.V0.
  echo.
  pause
  exit /b 1
)

%SENDA_PY% -m app.launcher
set "SENDA_RC=%ERRORLEVEL%"
if not "%SENDA_RC%"=="0" (
  echo.
  echo ERROR: SENDA.V0 no pudo iniciar.
  echo La ventana se mantendra abierta para que pueda leer el error.
  echo Revise tambien el archivo senda_v0.log dentro de la carpeta de datos de SENDA.V0.
  echo.
  pause
)
exit /b %SENDA_RC%
