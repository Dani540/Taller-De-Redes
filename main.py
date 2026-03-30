"""
Sala de Chat Hibrida TCP + UDP
==============================
Punto de entrada unico. Se encarga solo de:
  1. Crear el entorno virtual si no existe
  2. Instalar dependencias automaticamente
  3. Preguntar el modo de forma interactiva

Uso:
  python main.py              <- menu interactivo
  python main.py server       <- directo como servidor
  python main.py client       <- directo como cliente
  python main.py client 192.168.1.5
"""

import sys
import os
import subprocess
import platform

# ── Configuracion ─────────────────────────────────────────────────────────────
VENV_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv")


def _venv_python() -> str:
    """Retorna la ruta al ejecutable de Python dentro del venv."""
    if platform.system() == "Windows":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def _in_venv() -> bool:
    """True si estamos corriendo dentro de un entorno virtual."""
    return sys.prefix != sys.base_prefix


def _bootstrap() -> None:
    """
    Crea el venv, instala dependencias y se relanza dentro del venv.
    Solo se ejecuta una vez — la proxima ejecucion ya estara dentro del venv.
    """
    print("")
    print("Configurando entorno por primera vez...")
    print("")

    # Crear venv
    try:
        subprocess.check_call(
            [sys.executable, "-m", "venv", VENV_DIR],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        print("ERROR: No se pudo crear el entorno virtual.")
        print("Asegurate de tener Python 3.10+ instalado.")
        sys.exit(1)

    # Instalar dependencias
    pip = os.path.join(
        VENV_DIR,
        "Scripts" if platform.system() == "Windows" else "bin",
        "pip"
    )
    reqs = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")

    try:
        subprocess.check_call(
            [pip, "install", "-r", reqs, "--quiet"],
            stdout=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        print("ERROR: No se pudieron instalar las dependencias.")
        sys.exit(1)

    print("Entorno listo.")
    print("")

    # Relanzar este mismo script dentro del venv
    python = _venv_python()
    result = subprocess.run([python] + sys.argv)
    sys.exit(result.returncode)


def _ensure_venv() -> None:
    """
    Si no estamos en el venv, lo crea (si hace falta) y se relanza dentro.
    Despues de esto, el resto del script siempre corre en el venv.
    """
    if _in_venv():
        return

    if not os.path.exists(_venv_python()):
        _bootstrap()
    else:
        # El venv ya existe pero no estamos dentro — solo relanzar
        python = _venv_python()
        result = subprocess.run([python] + sys.argv)
        sys.exit(result.returncode)


# ── Menu interactivo ──────────────────────────────────────────────────────────

def _print_banner() -> None:
    print("")
    print("  +----------------------------------+")
    print("  |   Sala de Chat  TCP + UDP        |")
    print("  |   Sockets de Red -- 2025         |")
    print("  +----------------------------------+")
    print("")


def _ask_mode() -> tuple:
    """Pregunta el modo y host de forma interactiva. Retorna (modo, host)."""
    _print_banner()
    print("  [1]  Servidor")
    print("  [2]  Cliente")
    print("")

    while True:
        choice = input("  Selecciona (1/2): ").strip()
        if choice in ("1", "2"):
            break
        print("  Opcion invalida, ingresa 1 o 2.")

    if choice == "1":
        return "server", "localhost"

    # Modo cliente: preguntar host
    print("")
    host = input("  IP del servidor [localhost]: ").strip()
    if not host:
        host = "localhost"
    return "client", host


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    # Garantizar que corremos dentro del venv antes de importar nada externo
    _ensure_venv()

    # A partir de aca estamos en el venv — importar los modulos del proyecto
    import server
    import client

    # Determinar modo: argumento o menu interactivo
    args = sys.argv[1:]

    if not args:
        mode, host = _ask_mode()
    else:
        mode = args[0].lower()
        host = args[1] if len(args) > 1 else "localhost"

    if mode == "server":
        print("")
        server.main()

    elif mode == "client":
        client.TCP_HOST = host
        client.main()

    else:
        print(f"Modo invalido: '{mode}'. Usa 'server' o 'client'.")
        sys.exit(1)


if __name__ == "__main__":
    main()
