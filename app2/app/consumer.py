import pika
import json
from .services import process_***REMOVED***

def start_consuming():
    """
    Starts the RabbitMQ consumer.
    This function will connect to RabbitMQ, declare a queue, and start consuming messages.
    """
    # This is a simplified consumer. In a production environment, you'd want
    # to handle connection failures, retries, and acknowledgements more robustly.
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters('middleware'))
        channel = connection.channel()

        channel.queue_declare(queue='order_created', durable=True)

        def callback(ch, method, properties, body):
            print(" [x] Received %r" % body)
            order_data = json.loads(body)
            process_***REMOVED***(order_data)
            ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_consume(queue='order_created', on_message_callback=callback)

        print(' [*] Waiting for messages. To exit press CTRL+C')
        channel.start_consuming()
    except pika.exceptions.AMQPConnectionError as e:
        print(f"Could not connect to RabbitMQ: {e}")
        # In a real app, you'd have a retry mechanism here.

if __name__ == '__main__':
    start_consuming()
