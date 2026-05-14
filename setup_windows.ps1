$ErrorActionPreference = "Stop"

function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @("py", "-3")
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @("python")
    }
    return $null
}

$pythonCmd = Get-PythonCommand

if (-not $pythonCmd) {
    Write-Host ""
    Write-Host "Python 3 no esta instalado o no esta en PATH." -ForegroundColor Red
    Write-Host "Instalalo desde https://www.python.org/downloads/windows/" -ForegroundColor Yellow
    Write-Host "Durante la instalacion marca 'Add Python to PATH'." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Host "Usando interprete: $($pythonCmd -join ' ')" -ForegroundColor Cyan

if (-not (Test-Path ".\venv")) {
    Write-Host "Creando entorno virtual..." -ForegroundColor Cyan
    & $pythonCmd[0] @($pythonCmd[1..($pythonCmd.Length - 1)]) -m venv venv
} else {
    Write-Host "El entorno virtual ya existe." -ForegroundColor DarkYellow
}

$venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "No se encontro el Python del entorno virtual en $venvPython" -ForegroundColor Red
    exit 1
}

Write-Host "Actualizando pip..." -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip

Write-Host "Instalando dependencias del proyecto..." -ForegroundColor Cyan
& $venvPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")

Write-Host ""
Write-Host "Listo. Para ejecutar el bot:" -ForegroundColor Green
Write-Host "1. .\venv\Scripts\Activate.ps1"
Write-Host "2. python main.py"
Write-Host ""
Write-Host "Si PowerShell bloquea la activacion, ejecuta esta vez:" -ForegroundColor Yellow
Write-Host "Set-ExecutionPolicy -Scope Process Bypass"
