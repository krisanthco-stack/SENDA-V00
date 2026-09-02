@echo off
:menu
cls
echo =====================================
echo SENDA.V0 0.4.0 - MANTENIMIENTO
echo =====================================
echo 1. Instalar / Reparar
echo 2. Actualizar sin borrar datos
echo 3. Desinstalar
echo 4. Salir
set /p op=Seleccione: 
if "%op%"=="1" call "%~dp0INSTALAR_SENDA_V0.bat"
if "%op%"=="2" call "%~dp0ACTUALIZAR_SENDA_V0.bat"
if "%op%"=="3" call "%~dp0DESINSTALAR_SENDA_V0.bat"
if "%op%"=="4" exit /b 0
pause
goto menu
