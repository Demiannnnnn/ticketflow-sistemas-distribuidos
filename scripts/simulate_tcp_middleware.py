import socket
import json
import time
import random
import threading

# Configuración
HOST = 'localhost'
PORT = 6002

# Configuración para recibir notificaciones
NOTIFY_HOST = '0.0.0.0'
NOTIFY_PORT = 7002

def listen_for_notifications():
    """
    Servidor TCP simple que escucha notificaciones desde App2
    """
    print(f" [Middleware Listener] Esperando notificaciones en {NOTIFY_HOST}:{NOTIFY_PORT}...")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((NOTIFY_HOST, NOTIFY_PORT))
            s.listen()
            while True:
                conn, addr = s.accept()
                with conn:
                    # print(f" [Middleware Listener] Conexión desde {addr}")
                    buffer = ""
                    while True:
                        data = conn.recv(1024)
                        if not data:
                            break
                        buffer += data.decode('utf-8')
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            if line.strip():
                                try:
                                    msg = json.loads(line)
                                    print(f"\n [!!!] NOTIFICACIÓN RECIBIDA: {msg['type']}")
                                    print(f"       Datos: {msg['data']}")
                                    print(f"       Timestamp: {msg['timestamp']}\n")
                                except json.JSONDecodeError:
                                    print(f" [!] Error decodificando JSON: {line}")
        except Exception as e:
            print(f" [!] Error en listener de notificaciones: {e}")

def send_tcp_ticket(ticket_id, rut, price, event):
    print(f"--- Intentando enviar ticket {ticket_id} a {HOST}:{PORT} ---")
    try:
        # Crear un socket TCP/IP
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            print(f" [v] Conectado a {HOST}:{PORT}")
            
            data = {
                "id": ticket_id,
                "rut": rut,
                "price": price,
                "event": event
            }
            
            # El adaptador espera mensajes delimitados por salto de línea
            message = json.dumps(data) + "\n"
            
            s.sendall(message.encode('utf-8'))
            
            print(f" [x] Enviado: {message.strip()}")
            # Esperamos un poco antes de cerrar para asegurar que se envíe
            time.sleep(0.1) 
            
    except ConnectionRefusedError:
        print(f" [!] No se pudo conectar a {HOST}:{PORT}. ¿Está corriendo el servicio y Nginx?")
    except Exception as e:
        print(f" [!] Error: {e}")

if __name__ == '__main__':
    print("Simulador de Middleware TCP (Bidireccional)")
    print("Asegúrate de que en .env tengas MIDDLEWARE_TYPE=tcp_server")
    
    # Iniciar el listener de notificaciones en segundo plano
    listener_thread = threading.Thread(target=listen_for_notifications, daemon=True)
    listener_thread.start()
    
    # Dar tiempo al listener para arrancar
    time.sleep(1)
    
    # Enviar un par de tickets de prueba
    send_tcp_ticket(
        ticket_id=f"TCP-{random.randint(1000, 9999)}",
        rut=11223344, 
        price=7500, 
        event="Concierto TCP Rock"
    )
    
    time.sleep(1)
    
    send_tcp_ticket(
        ticket_id=f"TCP-{random.randint(1000, 9999)}",
        rut=55667788, 
        price=12000, 
        event="Gala de Sockets"
    )
    
    print("\n [i] El simulador seguirá corriendo para escuchar notificaciones.")
    print("     Presiona CTRL+C para salir.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nSaliendo...")

