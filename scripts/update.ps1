$ErrorActionPreference = 'Stop'

$SourceRoot = Split-Path -Parent $PSScriptRoot
$InstallRoot = Join-Path $env:LOCALAPPDATA 'Programs\SENDA.V0'
$DataRoot = Join-Path $env:LOCALAPPDATA 'SENDA.V0'

Write-Host ''
Write-Host 'SENDA.V0 - ACTUALIZACION' -ForegroundColor Cyan
Write-Host "Paquete nuevo: $SourceRoot"
Write-Host "Aplicacion:    $InstallRoot"
Write-Host "Datos:         $DataRoot"
Write-Host 'La actualizacion reemplaza solo codigo de la aplicacion y preserva todos los datos del usuario.'

if (-not (Test-Path $InstallRoot)) {
    throw 'SENDA.V0 no esta instalada. Ejecute INSTALAR_SENDA_V0.bat primero.'
}
if ((Resolve-Path $SourceRoot).Path -eq (Resolve-Path $InstallRoot).Path) {
    throw 'Ejecute ACTUALIZAR_SENDA_V0.bat desde el paquete NUEVO, no desde la instalacion actual.'
}

$folders = @('app','ui','vendor','scripts')
foreach ($name in $folders) {
    $src = Join-Path $SourceRoot $name
    if (-not (Test-Path $src)) { throw "Falta componente requerido: $name" }
    $dst = Join-Path $InstallRoot $name
    if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
    Copy-Item $src $dst -Recurse -Force
}

$files = @('INICIAR_SENDA_V0.bat','INSTALAR_SENDA_V0.bat','ACTUALIZAR_SENDA_V0.bat','DESINSTALAR_SENDA_V0.bat','pyproject.toml','README.md')
foreach ($name in $files) {
    $src = Join-Path $SourceRoot $name
    if (Test-Path $src) { Copy-Item $src (Join-Path $InstallRoot $name) -Force }
}

Write-Host ''
Write-Host 'ACTUALIZACION COMPLETADA.' -ForegroundColor Green
Write-Host "Se preserva la base, expedientes, importaciones, respaldos, exportaciones y logs en: $DataRoot"
