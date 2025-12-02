import socket
import json
import time
import random

# Configuración
HOST = 'localhost'
PORT = 6002

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
    print("Simulador de Middleware TCP (No-RabbitMQ)")
    print("Asegúrate de que en .env tengas MIDDLEWARE_TYPE=tcp_server")
    
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
