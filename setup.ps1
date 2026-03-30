# setup.ps1 — Ejecutar UNA SOLA VEZ despues de clonar el repo
# ---------------------------------------------------------------
# Si PowerShell bloquea la ejecucion de scripts, corre primero:
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

Write-Host ""
Write-Host "=== Sala de Chat TCP+UDP — Setup ===" -ForegroundColor Cyan
Write-Host ""

# Verificar que Python este instalado
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Python no encontrado. Instala Python 3.10+ desde https://python.org" -ForegroundColor Red
    exit 1
}

$version = python --version
Write-Host "Python encontrado: $version" -ForegroundColor Green

# Borrar venv anterior si existe (evita estado corrupto)
if (Test-Path "venv") {
    Write-Host "Borrando venv anterior..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force venv
}

# Crear venv limpio
Write-Host "Creando entorno virtual..." -ForegroundColor Yellow
python -m venv venv

if (-not (Test-Path ".\venv\Scripts\activate.ps1")) {
    Write-Host "ERROR: No se pudo crear el venv. Verifica tu instalacion de Python." -ForegroundColor Red
    exit 1
}

# Activar e instalar dependencias
Write-Host "Instalando dependencias..." -ForegroundColor Yellow
.\venv\Scripts\activate.ps1
pip install -r requirements.txt --quiet

Write-Host ""
Write-Host "Setup completo." -ForegroundColor Green
Write-Host ""
Write-Host "Para correr el proyecto:" -ForegroundColor Cyan
Write-Host "  .\run.ps1 server          <- Terminal 1" -ForegroundColor White
Write-Host "  .\run.ps1 client          <- Terminal 2" -ForegroundColor White
Write-Host "  .\run.ps1 client          <- Terminal 3" -ForegroundColor White
Write-Host ""
