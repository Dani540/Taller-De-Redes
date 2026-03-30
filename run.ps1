# run.ps1 — Ejecutar el servidor o el cliente
# ---------------------------------------------
# Uso:
#   .\run.ps1 server
#   .\run.ps1 client
#   .\run.ps1 client 192.168.1.42   (servidor en otra maquina)

param(
    [Parameter(Mandatory=$true, HelpMessage="Modo: server o client")]
    [ValidateSet("server", "client")]
    [string]$Mode,

    [Parameter(HelpMessage="IP del servidor (solo para modo client)")]
    [string]$ServerHost = "localhost"
)

# Verificar que el venv exista
if (-not (Test-Path ".\venv\Scripts\activate.ps1")) {
    Write-Host "ERROR: Entorno virtual no encontrado. Ejecuta primero: .\setup.ps1" -ForegroundColor Red
    exit 1
}

# Activar venv y correr
.\venv\Scripts\activate.ps1

if ($Mode -eq "server") {
    python main.py server
} else {
    python main.py client $ServerHost
}
