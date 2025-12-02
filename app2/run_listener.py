from app import create_app
from app.socket_listener import TicketSocketListener

app = create_app()
listener = TicketSocketListener()

if __name__ == '__main__':
    print("Starting Ticket Socket Listener...")
    listener.listen_loop(app)
