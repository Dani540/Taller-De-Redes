#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   SALA DE CHAT — Servidor Híbrido TCP + UDP                  ║
║   Universidad · Tarea de Sockets de Red                      ║
╠══════════════════════════════════════════════════════════════╣
║   TCP :9000  →  Conexiones, mensajes definitivos, broadcast  ║
║   UDP :9001  →  Borradores en tiempo real (keystroke a key)  ║
╚══════════════════════════════════════════════════════════════╝

Métodos POSIX demostrados (nomenclatura C/POSIX):
  int socket(int domain, int type, int protocol)
  int bind(int sockfd, const struct sockaddr *addr, socklen_t addrlen)
  int listen(int sockfd, int backlog)
  int accept(int sockfd, struct sockaddr *addr, socklen_t *addrlen)
  ssize_t recv(int sockfd, void *buf, size_t len, int flags)
  ssize_t recvfrom(int sockfd, void *buf, size_t len, int flags,
                   struct sockaddr *src_addr, socklen_t *addrlen)
  ssize_t send(int sockfd, const void *buf, size_t len, int flags)
  int close(int fd)

Protocolo de mensajes (servidor → cliente, TCP):
  "SYS:texto\n"             — mensajes de sistema (join/leave)
  "MSG:username\x00texto\n" — mensaje de chat definitivo
  "DRAFT:username\x00texto\n" — borrador en tiempo real (reenvío UDP→TCP)
  "ERR:texto\n"             — error de registro

Protocolo de mensajes (cliente → servidor, UDP):
  "username\x00borrador_actual" — datagrama por cada keystroke
"""

import socket
import threading
from datetime import datetime

# ── Parámetros de red ─────────────────────────────────────────────────────────
TCP_HOST     = ""   # INADDR_ANY: escucha en todas las interfaces
TCP_PORT     = 9000
UDP_PORT     = 9001
BUFFER       = 4096 # Tamaño del buffer de lectura en bytes
BACKLOG      = 10   # Máximo de conexiones pendientes en la cola de listen()
IDLE_TIMEOUT = 20   # Segundos sin clientes antes del apagado automático

# ── Estado compartido entre hilos ─────────────────────────────────────────────
clients: dict[str, socket.socket] = {}   # { username: socket_TCP }
clients_lock = threading.Lock()          # Mutex para acceso concurrente al dict

shutdown_event = threading.Event()       # Señal de apagado limpio

# Temporizador de inactividad (protegido por clients_lock)
had_clients: bool = False                # True desde que se conectó el primer cliente
idle_timer: threading.Timer | None = None


def _idle_shutdown() -> None:
    """Callback del temporizador: dispara el apagado automático."""
    print(f"\n[{ts()}] Sala vacía por {IDLE_TIMEOUT}s — cerrando servidor.")
    shutdown_event.set()


def _start_idle_timer() -> None:
    """Arranca el temporizador de inactividad. Debe llamarse bajo clients_lock."""
    global idle_timer
    idle_timer = threading.Timer(IDLE_TIMEOUT, _idle_shutdown)
    idle_timer.daemon = True
    idle_timer.start()
    print(f"[{ts()}] Sala vacía — cerrando en {IDLE_TIMEOUT}s si no hay conexiones.")


def _cancel_idle_timer() -> None:
    """Cancela el temporizador si está activo. Debe llamarse bajo clients_lock."""
    global idle_timer
    if idle_timer is not None:
        idle_timer.cancel()
        idle_timer = None


def ts() -> str:
    """Retorna la hora actual formateada para logs del servidor."""
    return datetime.now().strftime("%H:%M:%S")


def broadcast(tag: str, payload: str, exclude: str | None = None) -> None:
    """
    Envía un paquete a todos los clientes TCP registrados, excepto `exclude`.

    Formato del paquete: "TAG:payload\n"
    Limpia automáticamente los sockets muertos detectados al enviar.

    Equivalente POSIX:
      send(sockfd, buf, len, 0)  — para cada cliente en el registro
    """
    packet = f"{tag}:{payload}\n".encode()
    with clients_lock:
        dead: list[str] = []
        for name, sock in clients.items():
            if name == exclude:
                continue
            try:
                # sendall() llama a send() repetidamente hasta vaciar el buffer
                sock.sendall(packet)
            except OSError:
                dead.append(name)       # Marcar sin modificar el dict en el loop
        for name in dead:
            clients.pop(name)


def handle_tcp_client(conn: socket.socket, addr: tuple) -> None:
    """
    Hilo dedicado por cada cliente TCP.

    Ciclo de vida:
      REGISTRO → (recv usuario) → anunciar entrada
      CHAT     → (recv mensajes) → broadcast a los demás
      CIERRE   → anunciar salida → close()

    El OS crea un nuevo descriptor de archivo en accept() para `conn`,
    distinto del socket de escucha. Este hilo es dueño de ese descriptor.
    """
    username: str | None = None
    try:
        # ── REGISTRO: primer mensaje TCP = nombre de usuario ──────────────
        #   recv(sockfd, buf, BUFFER, 0)
        raw = conn.recv(BUFFER)
        if not raw:
            return

        username = raw.decode(errors="replace").strip()[:20]

        with clients_lock:
            if username in clients:
                conn.sendall(b"ERR:Nombre ya en uso. Elige otro.\n")
                return
            clients[username] = conn
            _cancel_idle_timer()   # Nuevo cliente: cancelar cuenta regresiva
            global had_clients
            had_clients = True

        n = len(clients)
        print(f"[{ts()}][TCP] {username!r} conectado desde {addr[0]}:{addr[1]}")

        # Confirmación de bienvenida al nuevo cliente
        conn.sendall(
            f"SYS:Bienvenido, {username}! Hay {n} usuario(s) en la sala.\n".encode()
        )
        # Anuncio al resto de la sala
        broadcast("SYS", f"[+] {username} entro a la sala.", exclude=username)

        # ── CHAT: loop de recepción de mensajes definitivos ───────────────
        while True:
            #   recv(sockfd, buf, BUFFER, 0) — bloquea hasta recibir o EOF
            data = conn.recv(BUFFER)
            if not data:
                break       # EOF: cliente cerró la conexión limpiamente

            text = data.decode(errors="replace").strip()
            if text:
                print(f"[{ts()}][TCP] {username}: {text}")
                broadcast("MSG", f"{username}\x00{text}", exclude=username)

    except (ConnectionResetError, BrokenPipeError, OSError):
        pass   # Desconexión abrupta — el finally limpia igual
    finally:
        # ── CIERRE ────────────────────────────────────────────────────────
        if username:
            with clients_lock:
                clients.pop(username, None)
                if had_clients and not clients:
                    _start_idle_timer()  # Sala vacía: iniciar cuenta regresiva
            broadcast("SYS", f"[-] {username} abandono la sala.")
            print(f"[{ts()}][TCP] {username!r} desconectado")
        #   close(sockfd) — libera el file descriptor
        conn.close()


def handle_udp(udp_sock: socket.socket) -> None:
    """
    Hilo único que procesa todos los datagramas UDP entrantes.

    Cada datagrama = estado completo del borrador del usuario en ese instante.
    Si se pierde un datagrama, el siguiente keystroke lo reemplaza → pérdida tolerable.

    Formato recibido: "username\x00borrador_actual"
    """
    while True:
        try:
            # recvfrom(sockfd, buf, BUFFER, 0, src_addr, addrlen)
            # Retorna (datos, (ip_origen, puerto_origen))
            data, addr = udp_sock.recvfrom(BUFFER)
            text = data.decode(errors="replace")

            if "\x00" not in text:
                continue

            username, draft = text.split("\x00", 1)
            username = username.strip()[:20]

            # Reenviar el borrador como paquete TCP a todos los demás clientes
            # Aquí ocurre la conversión UDP → TCP: el servidor actúa de puente
            broadcast("DRAFT", f"{username}\x00{draft}", exclude=username)

        except OSError:
            break


def main() -> None:
    # ── Socket TCP: SOCK_STREAM = confiable, orientado a conexión ─────────
    #   socket(AF_INET, SOCK_STREAM, 0)
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    #   bind(sockfd, {AF_INET, TCP_PORT, INADDR_ANY}, sizeof(addr))
    tcp_sock.bind((TCP_HOST, TCP_PORT))

    #   listen(sockfd, BACKLOG) — activa cola de conexiones pasivas
    tcp_sock.listen(BACKLOG)
    tcp_sock.settimeout(1.0)   # desbloquea accept() cada 1 s → permite Ctrl+C

    # ── Socket UDP: SOCK_DGRAM = sin conexión, datagramas, bajo overhead ──
    #   socket(AF_INET, SOCK_DGRAM, 0)
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    #   bind(sockfd, {AF_INET, UDP_PORT, INADDR_ANY}, sizeof(addr))
    # UDP también requiere bind() para recibir en un puerto fijo
    udp_sock.bind((TCP_HOST, UDP_PORT))

    print("╔══════════════════════════════════════════╗")
    print("║   Sala de Sockets — Servidor activo      ║")
    print("╠══════════════════════════════════════════╣")
    print(f"║  TCP  →  0.0.0.0:{TCP_PORT}  (mensajes)       ║")
    print(f"║  UDP  →  0.0.0.0:{UDP_PORT}  (drafts live)    ║")
    print("╚══════════════════════════════════════════╝")
    print("Esperando clientes... Ctrl+C para detener.\n")

    # Hilo daemon para UDP (termina cuando el proceso principal termina)
    threading.Thread(target=handle_udp, args=(udp_sock,), daemon=True).start()

    try:
        while True:
            #   accept(sockfd, addr, addrlen)
            # Bloquea hasta que llega una conexión, retorna (nuevo_fd, dirección)
            # Cada llamada a accept() crea un nuevo descriptor de archivo
            try:
                conn, addr = tcp_sock.accept()
            except socket.timeout:
                if shutdown_event.is_set():
                    break   # Temporizador de inactividad disparado
                continue    # Despertar periódico: volver a esperar

            # Cada cliente recibe su propio hilo para no bloquear el loop
            threading.Thread(
                target=handle_tcp_client,
                args=(conn, addr),
                daemon=True
            ).start()

    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        #   close(sockfd) — libera ambos file descriptors
        tcp_sock.close()
        udp_sock.close()


if __name__ == "__main__":
    main()
