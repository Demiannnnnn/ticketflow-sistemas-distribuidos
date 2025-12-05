import pika
import json
import os
import time
from .services import TicketService

class RabbitMQConsumer:
    def __init__(self):
        self.host = os.environ.get('RABBITMQ_HOST', 'rabbitmq')
        self.order_queue_name = 'orden_creada'
        self.reservation_queue_name = 'app1_reservations' # New queue for App1 reservations

    def connect(self):
        while True:
            try:
                connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.host))
                return connection
            except pika.exceptions.AMQPConnectionError:
                print(f"Could not connect to RabbitMQ at {self.host}. Retrying in 5s...")
                time.sleep(5)

    def callback(self, ch, method, properties, body):
        print(f" [x] Received from queue '{method.routing_key}': {body}")
        try:
            data = json.loads(body)
            with self.app.app_context():
                if method.routing_key == self.order_queue_name:
                    TicketService.process_order_from_middleware(data)
                elif method.routing_key == self.reservation_queue_name:
                    TicketService.receive_external_ticket(data)
                else:
                    print(f"Unknown queue '{method.routing_key}'. Message not processed.")
        except Exception as e:
            print(f"Error processing RabbitMQ message from '{method.routing_key}': {e}")

    def start(self, app):
        self.app = app
        connection = self.connect()
        channel = connection.channel()

        channel.queue_declare(queue=self.order_queue_name, durable=True)
        channel.queue_declare(queue=self.reservation_queue_name, durable=True) # Declare new queue

        channel.basic_consume(queue=self.order_queue_name, on_message_callback=self.callback, auto_ack=True)
        channel.basic_consume(queue=self.reservation_queue_name, on_message_callback=self.callback, auto_ack=True) # Consume from new queue

        print(f" [*] Waiting for messages in RabbitMQ queues '{self.order_queue_name}' and '{self.reservation_queue_name}'. To exit press CTRL+C")
        try:
            channel.start_consuming()
        except KeyboardInterrupt:
            channel.stop_consuming()
            connection.close()
        except Exception as e:
             print(f"Connection lost: {e}")
             # Reconnect logic could go here
