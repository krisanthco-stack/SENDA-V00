$ErrorActionPreference = 'Stop'

$SourceRoot = Split-Path -Parent $PSScriptRoot
$InstallRoot = Join-Path $env:LOCALAPPDATA 'Programs\SENDA.V0'
$DataRoot = Join-Path $env:LOCALAPPDATA 'SENDA.V0'

Write-Host ''
Write-Host 'SENDA.V0 - INSTALACION' -ForegroundColor Cyan
Write-Host "Origen:      $SourceRoot"
Write-Host "Aplicacion:  $InstallRoot"
Write-Host "Datos:       $DataRoot"
Write-Host 'Los datos se almacenan fuera de la aplicacion y se preservan durante instalar/actualizar.'

$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python -ErrorAction SilentlyContinue }
if (-not $python) { throw 'No se encontro Python 3. Instale Python 3 antes de instalar SENDA.V0.' }

New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null

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

$desktop = [Environment]::GetFolderPath('Desktop')
$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
$shell = New-Object -ComObject WScript.Shell
foreach ($linkPath in @((Join-Path $desktop 'SENDA.V0.lnk'), (Join-Path $startMenu 'SENDA.V0.lnk'))) {
    $shortcut = $shell.CreateShortcut($linkPath)
    $shortcut.TargetPath = Join-Path $InstallRoot 'INICIAR_SENDA_V0.bat'
    $shortcut.WorkingDirectory = $InstallRoot
    $shortcut.Description = 'SENDA.V0 - Gestion registral local'
    $shortcut.Save()
}

Write-Host ''
Write-Host 'INSTALACION COMPLETADA.' -ForegroundColor Green
Write-Host 'Puede iniciar SENDA.V0 desde el acceso directo del escritorio o menu Inicio.'
Write-Host "Los datos permaneceran en: $DataRoot"
