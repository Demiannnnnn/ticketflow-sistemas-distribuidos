import json
import pika
import time
from .services import TicketService
from .models import db
from flask import current_app

class TicketSocketListener:
    def __init__(self, host='rabbitmq', queue_name='new_ticket'):
        self.host = host
        self.queue_name = queue_name
        self.connection = None
        self.channel = None

    def connect_to_middleware(self):
        while True:
            try:
                self.connection = pika.BlockingConnection(pika.ConnectionParameters(self.host))
                self.channel = self.connection.channel()
                self.channel.queue_declare(queue=self.queue_name, durable=True)
                print(f"Connected to Middleware (RabbitMQ) on queue '{self.queue_name}'")
                return
            except pika.exceptions.AMQPConnectionError:
                print("Middleware not available, retrying in 5 seconds...")
                time.sleep(5)

    def on_ticket_received_event(self, ch, method, properties, body):
        print(f" [x] Received event: {body}")
        try:
            data = json.loads(body)
            # Necesitamos el contexto de la aplicación para usar DB
            # Esto se llamará desde dentro del contexto si se instancia correctamente,
            # o necesitamos pasar la app.
            # Una forma común es usar app.app_context() al invocar el servicio.
            
            # Asumimos que quien instancia esto maneja el contexto o lo pasamos.
            # Para simplificar, usaremos current_app si está disponible, o esperamos que
            # el loop se corra con contexto.
            
            # NOTA: Como esto corre en un hilo/proceso o loop bloqueante, 
            # hay que asegurar el contexto de Flask.
            
            # Aquí simulamos o usamos el servicio:
            with self.app.app_context():
                TicketService.receive_external_ticket(data)
                
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            print(f"Error processing message: {e}")
            # ch.basic_nack(delivery_tag=method.delivery_tag) # Optional

    def listen_loop(self, app):
        self.app = app
        self.connect_to_middleware()
        
        self.channel.basic_consume(
            queue=self.queue_name, 
            on_message_callback=self.on_ticket_received_event
        )
        
        print(' [*] Waiting for messages. To exit press CTRL+C')
        self.channel.start_consuming()
