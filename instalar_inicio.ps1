# Crea un acceso directo en la carpeta de Inicio de Windows para que
# Mi Panel de Tareas arranque automáticamente al encender la PC (sin consola).
#
# Uso:  powershell -ExecutionPolicy Bypass -File instalar_inicio.ps1
# Para quitarlo: borra "Mi Panel de Tareas.lnk" en  Win+R -> shell:startup

$carpeta = Split-Path -Parent $MyInvocation.MyCommand.Path
$script  = Join-Path $carpeta "tareas.py"

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) {
    Write-Host "No se encontró Python. Instálalo desde https://www.python.org" -ForegroundColor Red
    exit 1
}
$pythonw = Join-Path (Split-Path $python) "pythonw.exe"
if (-not (Test-Path $pythonw)) {
    Write-Host "No se encontró pythonw.exe junto a $python" -ForegroundColor Red
    exit 1
}

$lnk = Join-Path ([Environment]::GetFolderPath("Startup")) "Mi Panel de Tareas.lnk"
$acceso = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$acceso.TargetPath       = $pythonw
$acceso.Arguments        = "`"$script`""
$acceso.WorkingDirectory = $carpeta
$acceso.Description      = "Mi Panel de Tareas"
$acceso.Save()

Write-Host "Listo. El widget arrancará con Windows." -ForegroundColor Green
Write-Host "Acceso directo creado en: $lnk"
