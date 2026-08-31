import os
import json
import time
import socket


class MiddlewareAdapter:
    def listen(self, callback):
        raise NotImplementedError


class TCPSocketAdapter(MiddlewareAdapter):
    def __init__(self, host, port):
        self.host = host
        self.port = int(port)

    def listen(self, callback):
        while True:
            try:
                # Connect as a client to the middleware
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    print(f"Connecting to Generic Middleware at {self.host}:{self.port}...")
                    s.connect((self.host, self.port))
                    print(f"Connected to Middleware at {self.host}:{self.port}")

                    buffer = ""
                    while True:
                        data = s.recv(1024)
                        if not data:
                            break

                        # Assume newline delimited JSON for simplicity in generic streams
                        buffer += data.decode('utf-8')
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            if line.strip():
                                callback(line.encode('utf-8'))
            except ConnectionRefusedError:
                print(f"Connection refused by Middleware at {self.host}:{self.port}, retrying in 5s...")
                time.sleep(5)
            except Exception as e:
                print(f"Socket error: {e}, retrying in 5s...")
                time.sleep(5)


class TCPServerAdapter(MiddlewareAdapter):
    def __init__(self, port):
        self.port = int(port)

    def listen(self, callback):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Allow reuse of address
            s.bind(('0.0.0.0', self.port))
            s.listen()
            print(f"Listening for Ticket connections on 0.0.0.0:{self.port}...")

            while True:
                conn, addr = s.accept()
                with conn:
                    print(f"Connected by {addr}")
                    buffer = ""
                    while True:
                        data = conn.recv(1024)
                        if not data:
                            break
                        buffer += data.decode('utf-8')
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            if line.strip():
                                callback(line.encode('utf-8'))


class RabbitMQAdapter(MiddlewareAdapter):
    def __init__(self, host=None, port=None, queue_name='orden_creada', user=None, password=None):
        self.host = host or os.environ.get('RABBITMQ_HOST', 'rabbitmq')
        self.port = int(port or os.environ.get('RABBITMQ_PORT', 5672))
        self.queue_name = queue_name
        self.user = user or os.environ.get('RABBITMQ_USER', 'guest')
        self.password = password or os.environ.get('RABBITMQ_PASSWORD', 'guest')

    def listen(self, callback):
        print(f"Connecting to RabbitMQ at {self.host}:{self.port}, queue: {self.queue_name}...")
        while True:
            try:
                import pika
                credentials = pika.PlainCredentials(self.user, self.password)
                parameters = pika.ConnectionParameters(
                    host=self.host,
                    port=self.port,
                    credentials=credentials,
                    heartbeat=600,
                    blocked_connection_timeout=300
                )
                connection = pika.BlockingConnection(parameters)
                channel = connection.channel()

                channel.queue_declare(queue=self.queue_name, durable=True)
                channel.basic_qos(prefetch_count=1)

                print(f" [*] Waiting for orders on RabbitMQ queue '{self.queue_name}'...")

                def on_message(ch, method, properties, body):
                    try:
                        callback(body)
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                    except Exception as e:
                        print(f"Error handling RabbitMQ message: {e}")
                        ch.basic_ack(delivery_tag=method.delivery_tag)

                channel.basic_consume(queue=self.queue_name, on_message_callback=on_message)
                channel.start_consuming()

            except Exception as e:
                print(f"RabbitMQ connection/consumer error: {e}, retrying in 5s...")
                time.sleep(5)


def get_middleware_adapter():
    mw_type = os.environ.get('MIDDLEWARE_TYPE', 'rabbitmq').lower()

    if mw_type == 'rabbitmq':
        return RabbitMQAdapter()

    elif mw_type == 'tcp_socket':
        host = os.environ.get('MIDDLEWARE_HOST', 'middleware')
        port = os.environ.get('MIDDLEWARE_PORT', '9000')
        return TCPSocketAdapter(host, port)

    elif mw_type == 'tcp_server':
        port = os.environ.get('MIDDLEWARE_PORT', '6002')
        return TCPServerAdapter(port)

    else:
        raise ValueError(f"Unknown middleware type: {mw_type}")
