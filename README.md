# Sala de Chat Hibrida TCP + UDP
> Tarea de Sockets de Red — Taller de Redes — ICC717-1 — 2026

Implementacion de una sala de chat en tiempo real que combina dos protocolos:
- **TCP :9000** — mensajes definitivos (garantia de entrega)
- **UDP :9001** — borradores keystroke a keystroke (baja latencia)

---

## Requisitos

- Python 3.10 o superior
- El resto se configura automaticamente al correr `main.py`

---

## Correr el proyecto

Abrir **3 terminales separadas** en la carpeta del proyecto y en cada una ejecutar:

```bash
python main.py
```

La primera vez crea el entorno virtual e instala las dependencias automaticamente. Las veces siguientes va directo al menu:

```
  +----------------------------------+
  |   Sala de Chat  TCP + UDP        |
  |   Sockets de Red -- 2026         |
  +----------------------------------+

  [1]  Servidor
  [2]  Cliente

  Selecciona (1/2):
```

**Terminal 1** → elegir `1` (Servidor)  
**Terminal 2 y 3** → elegir `2` (Cliente)

### Servidor en otra maquina (red local)

```bash
# En la maquina del servidor
python main.py server

# En las otras maquinas
python main.py client 192.168.1.42
```

El modo tambien se puede pasar como argumento directo sin menu:

```bash
python main.py server
python main.py client
python main.py client 192.168.1.42
```

---

## Estructura del proyecto

```
Socket/
├── main.py          # Punto de entrada unico — menu interactivo + bootstrap del venv
├── server.py        # Servidor hibrido TCP+UDP con threading
├── client.py        # Cliente con interfaz curses
├── requirements.txt # windows-curses (solo Windows, ignorado en Linux/macOS)
└── .gitignore
```

El entorno virtual (`venv/`) se crea automaticamente en la carpeta del proyecto la primera vez que se corre `main.py`. No se sube al repositorio.

---

## Los 10 metodos de socket

La API POSIX de sockets define un conjunto de llamadas al sistema operativo que abstraen la comunicacion de red. A continuacion se detalla donde y como se usa cada una en este proyecto.

---

### `socket(int domain, int type, int protocol)`

Crea un nuevo socket y retorna un **descriptor de archivo (fd)** — un numero entero que el kernel usa para identificar el recurso. No establece ninguna conexion, solo reserva la estructura interna.

| Archivo | Linea | Uso |
|---------|-------|-----|
| `server.py` | `main()` | `socket.socket(AF_INET, SOCK_STREAM)` — crea el socket TCP de escucha |
| `server.py` | `main()` | `socket.socket(AF_INET, SOCK_DGRAM)` — crea el socket UDP de datagramas |
| `client.py` | `main()` | `socket.socket(AF_INET, SOCK_STREAM)` — crea el socket TCP del cliente |
| `client.py` | `main()` | `socket.socket(AF_INET, SOCK_DGRAM)` — crea el socket UDP para borradores |

`SOCK_STREAM` = TCP (orientado a conexion). `SOCK_DGRAM` = UDP (datagramas sin conexion).

---

### `bind(int sockfd, const struct sockaddr *addr, socklen_t addrlen)`

Asigna una direccion local (IP + puerto) al socket. Sin `bind()`, el OS asigna un puerto efimero aleatorio, lo que impide que otros procesos sepan donde conectarse.

| Archivo | Linea | Uso |
|---------|-------|-----|
| `server.py` | `main()` | `tcp_sock.bind(("", 9000))` — fija el servidor TCP en el puerto 9000 en todas las interfaces |
| `server.py` | `main()` | `udp_sock.bind(("", 9001))` — fija el receptor UDP en el puerto 9001 |

El cliente **no llama** `bind()` en ningun socket — deja que el OS asigne puertos efimeros automaticamente, lo cual es el comportamiento correcto para un cliente.

---

### `listen(int sockfd, int backlog)`

Pone el socket TCP en modo de **escucha pasiva**. El parametro `backlog` define cuantas conexiones pueden esperar en la cola antes de ser aceptadas con `accept()`. Solo aplica a TCP — no existe en UDP.

| Archivo | Linea | Uso |
|---------|-------|-----|
| `server.py` | `main()` | `tcp_sock.listen(BACKLOG)` — activa la cola con capacidad para 10 conexiones pendientes |

---

### `accept(int sockfd, struct sockaddr *addr, socklen_t *addrlen)`

Extrae la primera conexion de la cola de `listen()` y crea un **nuevo fd** dedicado a esa conexion. El socket original de escucha no se toca — sigue esperando mas conexiones. Este nuevo fd es el que se le pasa al hilo del cliente.

| Archivo | Linea | Uso |
|---------|-------|-----|
| `server.py` | `main()` | `conn, addr = tcp_sock.accept()` — retorna `conn` (nuevo fd) y `addr` (IP:puerto del cliente) |

Cada llamada a `accept()` genera un fd distinto, lo que permite manejar multiples clientes en paralelo con un hilo por fd.

---

### `connect(int sockfd, const struct sockaddr *addr, socklen_t addrlen)`

Inicia el **3-way handshake TCP** con el servidor (SYN → SYN-ACK → ACK). Bloquea hasta que la conexion queda establecida o falla. Solo aplica al socket TCP del cliente.

| Archivo | Linea | Uso |
|---------|-------|-----|
| `client.py` | `main()` | `tcp_sock.connect((TCP_HOST, TCP_PORT))` — conecta al servidor en el puerto 9000 |

El socket UDP del cliente **no usa** `connect()` — `sendto()` especifica el destino en cada envio, que es la esencia del protocolo sin conexion.

---

### `send(int sockfd, const void *buf, size_t len, int flags)`

Escribe datos en el stream TCP. A diferencia de `sendall()`, puede retornar habiendo enviado solo una parte del buffer si el buffer interno del kernel esta lleno. En Python, `sendall()` llama a `send()` en loop hasta vaciar el buffer completo.

| Archivo | Linea | Uso |
|---------|-------|-----|
| `server.py` | `broadcast()` | `sock.sendall(packet)` — envia el paquete completo a cada cliente TCP registrado |
| `client.py` | `send_tcp()` | `tcp_sock.sendall(text.encode())` — envia el mensaje definitivo al servidor al presionar Enter |

Se usa `sendall()` y no `send()` porque el protocolo delimita mensajes con `\n` — un envio parcial corromperia el delimitador y romperia el parsing en el receptor.

---

### `recv(int sockfd, void *buf, size_t len, int flags)`

Lee datos del stream TCP. **Bloquea** hasta que haya al menos 1 byte disponible o el otro lado cierre la conexion. Retorna `b""` (cadena vacia) cuando detecta EOF — es decir, cuando el otro lado cerro la conexion.

| Archivo | Linea | Uso |
|---------|-------|-----|
| `server.py` | `handle_tcp_client()` | `raw = conn.recv(BUFFER)` — recibe el username inicial del cliente |
| `server.py` | `handle_tcp_client()` | `data = conn.recv(BUFFER)` — recibe mensajes del cliente en el loop principal |
| `client.py` | `receive_loop()` | `chunk = tcp_sock.recv(BUFFER)` — recibe broadcasts del servidor en hilo dedicado |

El patron `if not data: break` en ambos archivos es la deteccion de **EOF**: cuando el cliente se desconecta, el kernel envia un paquete TCP FIN, y `recv()` retorna `b""` en el servidor.

---

### `sendto(int sockfd, const void *buf, size_t len, int flags, const struct sockaddr *dest_addr, socklen_t addrlen)`

Envia un datagrama UDP especificando el destino directamente en cada llamada. No requiere `connect()` previo — cada llamada es independiente y puede ir a un destino distinto.

| Archivo | Linea | Uso |
|---------|-------|-----|
| `client.py` | `send_udp()` | `udp_sock.sendto(payload, (TCP_HOST, UDP_PORT))` — envia el borrador actual al servidor con cada keystroke |

Cada paquete UDP contiene el estado completo del borrador (`username\x00texto`). Si se pierde un paquete, el siguiente keystroke envia el estado actualizado — la perdida es tolerable.

---

### `recvfrom(int sockfd, void *buf, size_t len, int flags, struct sockaddr *src_addr, socklen_t *addrlen)`

Lee un datagrama UDP y retorna tambien la **direccion de origen** (IP + puerto del emisor). Es esencialmente un `recv()` extendido para sockets sin conexion.

| Archivo | Linea | Uso |
|---------|-------|-----|
| `server.py` | `handle_udp()` | `data, addr = udp_sock.recvfrom(BUFFER)` — recibe borradores de cualquier cliente en el puerto 9001 |

El servidor usa un unico hilo para todos los datagramas UDP, ya que `recvfrom()` retorna la direccion de origen en cada llamada — no es necesario un fd por cliente como en TCP.

---

### `close(int fd)`

Libera el descriptor de archivo. En conexiones TCP activas, envia un paquete **FIN** al otro lado para iniciar el cierre limpio de la conexion. El kernel libera todos los buffers asociados al fd.

| Archivo | Linea | Uso |
|---------|-------|-----|
| `server.py` | `handle_tcp_client()` — bloque `finally` | `conn.close()` — libera el fd del cliente al desconectarse |
| `server.py` | `main()` — bloque `finally` | `tcp_sock.close()` y `udp_sock.close()` — libera ambos fds del servidor al detenerlo |
| `client.py` | `main()` — bloque `finally` | `tcp_sock.close()` y `udp_sock.close()` — libera los fds del cliente al salir |

El uso de bloques `finally` garantiza que `close()` se llame incluso si ocurre una excepcion — evitando fugas de descriptores de archivo.
