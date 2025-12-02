import socket
import json
import os
from threading import Thread

class NotificationClient:
    @staticmethod
    def send_event(event_type, ticket_data):
        """
        Envía una notificación al middleware de forma asíncrona (fuego y olvido)
        para no bloquear la petición web del usuario.
        """
        payload = {
            "type": event_type,
            "data": ticket_data,
            "timestamp": str(os.times()) # Simple timestamp
        }
        
        # Ejecutar en un hilo separado para no bloquear
        thread = Thread(target=NotificationClient._send_internal, args=(payload,))
        thread.start()

    @staticmethod
    def _send_internal(payload):
        host = os.environ.get('MIDDLEWARE_NOTIFY_HOST', '172.17.0.1')
        port = int(os.environ.get('MIDDLEWARE_NOTIFY_PORT', 7002))
        
        print(f" [->] Sending notification to Middleware at {host}:{port}...")
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5) # Timeout de 5 segundos
                s.connect((host, port))
                
                message = json.dumps(payload) + "\n"
                s.sendall(message.encode('utf-8'))
                print(f" [->] Notification Sent: {payload['type']}")
        except Exception as e:
            print(f" [!] Failed to send notification: {e}")

