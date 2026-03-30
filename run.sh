#!/bin/bash
# run.sh — Ejecutar el servidor o el cliente (Linux / macOS)
# -----------------------------------------------------------
# Uso:
#   ./run.sh server
#   ./run.sh client
#   ./run.sh client 192.168.1.42   (servidor en otra maquina)

MODE=$1
HOST=${2:-localhost}

if [ -z "$MODE" ]; then
    echo "Uso: ./run.sh server | client [host]"
    exit 1
fi

if [ ! -f "venv/bin/activate" ]; then
    echo "ERROR: Entorno virtual no encontrado. Ejecuta primero: ./setup.sh"
    exit 1
fi

source venv/bin/activate

if [ "$MODE" = "server" ]; then
    python main.py server
elif [ "$MODE" = "client" ]; then
    python main.py client "$HOST"
else
    echo "Modo invalido: $MODE. Usa 'server' o 'client'."
    exit 1
fi
