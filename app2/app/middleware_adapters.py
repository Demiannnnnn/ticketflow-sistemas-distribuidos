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


def get_middleware_adapter():
    mw_type = os.environ.get('MIDDLEWARE_TYPE', 'tcp_server').lower()

    if mw_type == 'tcp_socket':
        host = os.environ.get('MIDDLEWARE_HOST', 'middleware')
        port = os.environ.get('MIDDLEWARE_PORT', '9000')
        return TCPSocketAdapter(host, port)

    elif mw_type == 'tcp_server':
        port = os.environ.get('MIDDLEWARE_PORT', '6002')
        return TCPServerAdapter(port)

    else:
        raise ValueError(f"Unknown middleware type: {mw_type}")
