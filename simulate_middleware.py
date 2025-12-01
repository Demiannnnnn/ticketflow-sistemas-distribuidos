import pika
import json
import time

# Configuración para conectar desde el HOST hacia el Docker
# RabbitMQ expone el puerto 5672 en localhost según el docker-compose.yml
RABBITMQ_HOST = 'localhost' 
QUEUE_NAME = 'new_ticket'

def send_ticket(ticket_id, rut, price, event):
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()

        # Declarar la cola por si acaso no existe (aunque el app2 ya la crea)
        channel.queue_declare(queue=QUEUE_NAME, durable=True)

        data = {
            "id": ticket_id,
            "rut": rut,
            "price": price,
            "event": event
        }

        message = json.dumps(data)
        
        channel.basic_publish(
            exchange='',
            routing_key=QUEUE_NAME,
            body=message
        )
        
        print(f" [x] Enviado ticket ID: {ticket_id} para RUT: {rut}")
        print(f"     Payload: {message}")
        
        connection.close()
        
    except Exception as e:
        print(f" [!] Error conectando a RabbitMQ: {e}")
        print("     Asegúrate de que el contenedor 'rabbitmq' esté corriendo y expuesto en el puerto 5672.")

if __name__ == '__main__':
    # Ejemplo: Crear ticket para un RUT que quizás no existe (creará Placeholder)
    # O usa un RUT registrado para vincularlo.
    print("--- Simulando Middleware ---")
    send_ticket(
        ticket_id="MW-TEST-001", 
        rut=9999999, 
        price=5000, 
        event="Lollapalooza 2025"
    )
    
    time.sleep(1)
    
    send_ticket(
        ticket_id="MW-TEST-002", 
        rut=8888888, 
        price=3500, 
        event="Tech Conference"
    )
