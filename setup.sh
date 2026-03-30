#!/bin/bash
# setup.sh — Ejecutar UNA SOLA VEZ despues de clonar el repo (Linux / macOS)

echo ""
echo "=== Sala de Chat TCP+UDP — Setup ==="
echo ""

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 no encontrado. Instala Python 3.10+ desde https://python.org"
    exit 1
fi

echo "Python encontrado: $(python3 --version)"

# Borrar venv anterior si existe
if [ -d "venv" ]; then
    echo "Borrando venv anterior..."
    rm -rf venv
fi

# Crear venv
echo "Creando entorno virtual..."
python3 -m venv venv

# Activar e instalar
echo "Instalando dependencias..."
source venv/bin/activate
pip install -r requirements.txt --quiet

echo ""
echo "Setup completo."
echo ""
echo "Para correr el proyecto:"
echo "  ./run.sh server          <- Terminal 1"
echo "  ./run.sh client          <- Terminal 2"
echo "  ./run.sh client          <- Terminal 3"
echo ""
