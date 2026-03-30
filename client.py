#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   SALA DE CHAT — Cliente Híbrido TCP + UDP                   ║
║   Universidad · Tarea de Sockets de Red                      ║
╚══════════════════════════════════════════════════════════════╝

Canales de comunicación:
  TCP :9000  →  connect() + sendall()  — mensaje al presionar Enter
               Garantía de entrega, orden, sin pérdidas.

  UDP :9001  →  sendto()              — borrador por cada keystroke
               Sin conexión, sin ACK. Si se pierde un paquete, el
               siguiente keystroke lo corrige igual → pérdida tolerable.

Interfaz terminal (curses):
  ┌─────────────── SALA DE SOCKETS | usuario | TCP:9000 UDP:9001 ───┐
  │  [10:30] [+] Juan entró a la sala                    (verde)    │
  │  [10:31] Ana: Hola, qué tal?                        (blanco)   │
  │  [10:31] Yo: Bien, gracias!                        (magenta)   │
  ├───────────── [UDP] ✏ Ana: "Todo bien y..."  ──────────────────┤
  │  [TCP→ Enter]   [UDP→ cada tecla]   >  tu mensaje aquí|        │
  └────────────────────────────────────────────────────────────────┘

  La franja [UDP] se actualiza en tiempo real sin agregar nuevas líneas.
  Los mensajes definitivos aparecen en el área de chat al recibir TCP.
"""

import curses
import socket
import threading
import sys
import time
from datetime import datetime

# ── Configuración de red ──────────────────────────────────────────────────────
TCP_HOST = "localhost"   # Cambiar a IP del servidor para red local
TCP_PORT = 9000
UDP_PORT = 9001
BUFFER   = 4096

# ── Estado compartido entre hilo de red y hilo de UI ─────────────────────────
messages: list[tuple[str, str, str]] = []   # [(timestamp, tag, texto)]
drafts:   dict[str, str]              = {}   # { username: borrador_actual }
state_lock = threading.Lock()
running = True

# Sockets (inicializados en main, usados en hilos)
username: str                  = ""
tcp_sock: socket.socket | None = None
udp_sock: socket.socket | None = None


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


# ── Hilo de recepción TCP ─────────────────────────────────────────────────────

def receive_loop() -> None:
    """
    Hilo dedicado a leer el stream TCP del servidor.

    Lee continuamente con recv(), acumula en un buffer de texto,
    y parsea paquetes completos delimitados por '\n'.

    Actualiza `messages` y `drafts` bajo lock para que la UI
    pueda leer snapshots consistentes.
    """
    global running
    buf = ""
    while running:
        try:
            #   recv(sockfd, buf, BUFFER, 0) — bloquea hasta recibir datos
            chunk = tcp_sock.recv(BUFFER).decode(errors="replace")
            if not chunk:
                break   # EOF: servidor cerró la conexión

            buf += chunk
            # Parsear paquetes completos (delimitados por \n)
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                if ":" not in line:
                    continue

                tag, _, payload = line.partition(":")
                tag = tag.strip()

                with state_lock:
                    if tag == "SYS":
                        messages.append((ts(), "SYS", payload))

                    elif tag == "MSG":
                        # Payload: "sender\x00texto"
                        if "\x00" in payload:
                            sender, text = payload.split("\x00", 1)
                            drafts.pop(sender, None)   # Limpiar draft al recibir msg
                            messages.append((ts(), "MSG", f"{sender}: {text}"))
                        else:
                            messages.append((ts(), "MSG", payload))

                    elif tag == "DRAFT":
                        # Payload: "sender\x00borrador" (reenvío UDP→TCP del servidor)
                        if "\x00" in payload:
                            sender, draft = payload.split("\x00", 1)
                            if draft:
                                drafts[sender] = draft
                            else:
                                drafts.pop(sender, None)   # Draft vacío = dejó de escribir

                    elif tag == "ERR":
                        messages.append((ts(), "ERR", payload))
                        running = False
                        return

        except OSError:
            break

    with state_lock:
        messages.append((ts(), "SYS", "Desconectado del servidor."))
    running = False


# ── Funciones de envío ────────────────────────────────────────────────────────

def send_tcp(text: str) -> None:
    """
    Envía un mensaje definitivo por TCP al presionar Enter.
    send(sockfd, buf, len, 0) — garantiza entrega y orden.
    """
    try:
        tcp_sock.sendall(text.encode())
    except OSError:
        pass


def send_udp(draft: str) -> None:
    """
    Envía el borrador actual por UDP con cada keystroke.
    sendto(sockfd, buf, len, 0, dest_addr, addrlen) — sin conexión previa.

    No se usa connect() en el UDP socket — sendto() especifica el
    destino directamente, lo que es la esencia del protocolo DGRAM.
    """
    try:
        payload = f"{username}\x00{draft}".encode()
        udp_sock.sendto(payload, (TCP_HOST, UDP_PORT))
    except OSError:
        pass


# ── Índices de pares de colores curses ────────────────────────────────────────
COL_HEADER = 1   # Blanco sobre azul  — barra de título
COL_SYS    = 2   # Verde              — mensajes del sistema (join/leave)
COL_MSG    = 3   # Blanco             — mensajes de chat (TCP)
COL_DRAFT  = 4   # Amarillo           — borradores en tiempo real (UDP)
COL_PROMPT = 5   # Cyan               — prompt de entrada
COL_ERR    = 6   # Rojo               — errores
COL_ME     = 7   # Magenta            — mis propios mensajes


# ── Funciones de renderizado ──────────────────────────────────────────────────

def draw_header(win, w: int) -> None:
    """Dibuja la barra de título con info de protocolo y usuario."""
    win.erase()
    title = f" SALA DE SOCKETS  |  {username}  |  TCP:{TCP_PORT}  UDP:{UDP_PORT} "
    try:
        win.addstr(0, 0, title.ljust(w)[:w],
                   curses.color_pair(COL_HEADER) | curses.A_BOLD)
    except curses.error:
        pass
    win.noutrefresh()


def draw_chat(win, chat_h: int, w: int, msg_list: list) -> None:
    """
    Dibuja el área de mensajes TCP.
    Muestra los últimos `chat_h` mensajes con timestamp y color por tipo.
    """
    win.erase()
    visible = msg_list[-chat_h:] if len(msg_list) > chat_h else msg_list

    color_map = {
        "SYS": COL_SYS,
        "MSG": COL_MSG,
        "ERR": COL_ERR,
        "ME":  COL_ME,
    }

    for row, (t, tag, text) in enumerate(visible):
        if row >= chat_h:
            break
        color = color_map.get(tag, COL_MSG)
        prefix = f"[{t}] "
        try:
            win.addstr(row, 0, prefix, curses.A_DIM)
            win.addstr(row, len(prefix),
                       text[:w - len(prefix) - 1],
                       curses.color_pair(color))
        except curses.error:
            pass
    win.noutrefresh()


def draw_draft_bar(win, w: int, draft_dict: dict) -> None:
    """
    Dibuja la barra de borradores UDP.
    Se actualiza in-place: no agrega nuevas líneas, reemplaza el contenido.
    Muestra todos los usuarios que están escribiendo simultáneamente.
    """
    win.erase()
    label = " [UDP] "
    try:
        if draft_dict:
            parts = []
            for u, d in draft_dict.items():
                short = d[:20] + ("..." if len(d) > 20 else "")
                parts.append(f"✏ {u}: \"{short}\"")
            content = "  |  ".join(parts)
            win.addstr(0, 0, label, curses.A_DIM)
            win.addstr(0, len(label), content[:w - len(label) - 1],
                       curses.color_pair(COL_DRAFT))
        else:
            win.addstr(0, 0, (label + "Sin actividad de escritura")[:w - 1],
                       curses.A_DIM)
    except curses.error:
        pass
    win.noutrefresh()


def draw_input(win, w: int, draft: str) -> None:
    """
    Dibuja el área de entrada del usuario.
    Línea superior: etiquetas de protocolo.
    Línea inferior: prompt + borrador actual del usuario.
    """
    win.erase()
    sep = " [TCP → Enter]   [UDP → cada tecla] "
    prompt = " > "
    try:
        win.addstr(0, 0, sep[:w - 1], curses.A_DIM)

        win.addstr(1, 0, prompt,
                   curses.color_pair(COL_PROMPT) | curses.A_BOLD)
        visible = draft[-(w - len(prompt) - 2):]
        win.addstr(1, len(prompt), visible[:w - len(prompt) - 1],
                   curses.color_pair(COL_MSG))
        win.move(1, min(len(prompt) + len(visible), w - 1))
    except curses.error:
        pass
    win.noutrefresh()


# ── UI principal curses ───────────────────────────────────────────────────────

def chat_ui(stdscr) -> None:
    """
    Loop principal de la interfaz curses.

    Layout (4 zonas):
      header_win (1 fila)   — título y protocolo
      chat_win   (N filas)  — mensajes TCP recibidos (scrollable)
      draft_win  (1 fila)   — borradores UDP en tiempo real
      input_win  (2 filas)  — entrada del usuario
    """
    global running

    curses.curs_set(1)
    curses.start_color()
    curses.use_default_colors()

    curses.init_pair(COL_HEADER, curses.COLOR_WHITE,   curses.COLOR_BLUE)
    curses.init_pair(COL_SYS,   curses.COLOR_GREEN,   -1)
    curses.init_pair(COL_MSG,   curses.COLOR_WHITE,    -1)
    curses.init_pair(COL_DRAFT, curses.COLOR_YELLOW,   -1)
    curses.init_pair(COL_PROMPT, curses.COLOR_CYAN,    -1)
    curses.init_pair(COL_ERR,   curses.COLOR_RED,      -1)
    curses.init_pair(COL_ME,    curses.COLOR_MAGENTA,  -1)

    H, W = stdscr.getmaxyx()
    HEADER_H = 1
    INPUT_H  = 2
    DRAFT_H  = 1

    def make_windows(H, W):
        chat_h = max(1, H - HEADER_H - INPUT_H - DRAFT_H)
        hw = curses.newwin(HEADER_H, W, 0, 0)
        cw = curses.newwin(chat_h,   W, HEADER_H, 0)
        dw = curses.newwin(DRAFT_H,  W, HEADER_H + chat_h, 0)
        iw = curses.newwin(INPUT_H,  W, HEADER_H + chat_h + DRAFT_H, 0)
        iw.keypad(True)    # Habilita teclas especiales (flechas, backspace, etc.)
        iw.timeout(50)     # get_wch() no bloquea más de 50ms → ~20fps de UI
        return hw, cw, dw, iw, chat_h

    header_win, chat_win, draft_win, input_win, chat_h = make_windows(H, W)

    # Lanzar hilo de recepción TCP (independiente del hilo de UI)
    threading.Thread(target=receive_loop, daemon=True).start()

    draft_buf = ""
    draw_header(header_win, W)

    while running:
        # Snapshot thread-safe: evita que el hilo de red modifique la lista
        # mientras la estamos leyendo para dibujar
        with state_lock:
            msg_snap   = list(messages)
            draft_snap = dict(drafts)

        draw_chat(chat_win, chat_h, W, msg_snap)
        draw_draft_bar(draft_win, W, draft_snap)
        draw_input(input_win, W, draft_buf)
        curses.doupdate()   # Un solo refresh de pantalla al final del frame

        # Leer tecla (no bloqueante — timeout 50ms)
        try:
            ch = input_win.get_wch()
        except curses.error:
            continue   # Sin tecla en este frame, continuar loop

        # ── Procesar tecla ────────────────────────────────────────────────
        if isinstance(ch, int):
            if ch in (curses.KEY_BACKSPACE, 127):
                if draft_buf:
                    draft_buf = draft_buf[:-1]
                    send_udp(draft_buf)          # UDP: borrador actualizado

            elif ch == curses.KEY_RESIZE:
                # Terminal redimensionado → reconstruir ventanas
                H, W = stdscr.getmaxyx()
                stdscr.clear()
                stdscr.refresh()
                header_win, chat_win, draft_win, input_win, chat_h = \
                    make_windows(H, W)
                draw_header(header_win, W)

        elif isinstance(ch, str):
            if ch in ("\n", "\r"):
                # ── ENTER: envío definitivo por TCP ───────────────────────
                text = draft_buf.strip()
                if text:
                    send_tcp(text)              # TCP: garantía de entrega
                    send_udp("")               # UDP: limpiar draft en otros clientes
                    with state_lock:
                        messages.append((ts(), "ME", f"Yo: {text}"))
                        drafts.pop(username, None)
                    draft_buf = ""

            elif ch in ("\x03", "\x04"):
                break   # Ctrl+C / Ctrl+D → salir limpiamente

            elif ord(ch) >= 32:
                # ── KEYSTROKE: envío de borrador por UDP ──────────────────
                draft_buf += ch
                send_udp(draft_buf)            # UDP: sin esperar confirmación

    running = False


# ── Punto de entrada ──────────────────────────────────────────────────────────

def main() -> None:
    global username, tcp_sock, udp_sock

    print("╔══════════════════════════════════════════╗")
    print("║   Sala de Sockets — Cliente              ║")
    print("╚══════════════════════════════════════════╝")
    username = input("Tu nombre de usuario: ").strip()
    if not username:
        print("Nombre invalido.")
        sys.exit(1)

    # ── Crear y conectar socket TCP ───────────────────────────────────────
    #   socket(AF_INET, SOCK_STREAM, 0)
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        #   connect(sockfd, {AF_INET, TCP_PORT, TCP_HOST}, sizeof(addr))
        # Inicia el 3-way handshake TCP (SYN → SYN-ACK → ACK)
        tcp_sock.connect((TCP_HOST, TCP_PORT))
    except ConnectionRefusedError:
        print(f"Error: no hay servidor en {TCP_HOST}:{TCP_PORT}")
        print("Asegurate de ejecutar server.py primero.")
        sys.exit(1)

    # Primer mensaje TCP = registro del username en el servidor
    tcp_sock.sendall(username.encode())

    # ── Crear socket UDP (sin conexión) ───────────────────────────────────
    #   socket(AF_INET, SOCK_DGRAM, 0)
    # SOCK_DGRAM no requiere connect() — sendto() especifica destino por envío
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print(f"Conectado como {username!r}. Iniciando interfaz...")
    time.sleep(0.3)

    try:
        curses.wrapper(chat_ui)   # Inicializa curses, llama a chat_ui, restaura terminal
    except KeyboardInterrupt:
        pass
    finally:
        #   close(sockfd) — libera ambos file descriptors
        tcp_sock.close()
        udp_sock.close()
        print("\nConexion cerrada. Hasta luego!")


if __name__ == "__main__":
    main()
