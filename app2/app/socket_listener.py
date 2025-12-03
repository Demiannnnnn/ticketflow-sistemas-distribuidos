import json
import os
from .services import TicketService
from .middleware_adapters import get_middleware_adapter

class TicketSocketListener:
    def __init__(self):
        self.adapter = get_middleware_adapter()

    def process_message(self, body):
        print(f" [x] Received event: {body}")
        try:
            data = json.loads(body)
            with self.app.app_context():
                TicketService.receive_external_ticket(data)
        except Exception as e:
            print(f"Error processing message: {e}")

    def listen_loop(self, app):
        self.app = app
        print(' [*] Starting Middleware Listener...')
        self.adapter.listen(self.process_message)
