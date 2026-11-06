import json
import socket
import threading

import pytest

from app.middleware_adapters import TCPServerAdapter, TCPSocketAdapter, get_middleware_adapter
from app.models import Ticket
from app.notification_client import NotificationClient
from app.socket_listener import TicketSocketListener


def test_factory_de_adaptadores(monkeypatch):
    monkeypatch.delenv("MIDDLEWARE_TYPE", raising=False)
    monkeypatch.delenv("MIDDLEWARE_PORT", raising=False)
    a = get_middleware_adapter()
    assert isinstance(a, TCPServerAdapter) and a.port == 6002

    monkeypatch.setenv("MIDDLEWARE_TYPE", "TCP_SOCKET")
    monkeypatch.setenv("MIDDLEWARE_HOST", "mw")
    monkeypatch.setenv("MIDDLEWARE_PORT", "9100")
    b = get_middleware_adapter()
    assert isinstance(b, TCPSocketAdapter) and (b.host, b.port) == ("mw", 9100)

    monkeypatch.setenv("MIDDLEWARE_TYPE", "rabbitmq")
    with pytest.raises(ValueError):
        get_middleware_adapter()


def _puerto_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_tcp_server_entrega_lineas_json_completas():
    """Los mensajes llegan delimitados por \\n aunque vengan partidos en varios envíos."""
    port = _puerto_libre()
    recibidos = []
    listo = threading.Event()

    def callback(line):
        recibidos.append(json.loads(line))
        if len(recibidos) == 2:
            listo.set()

    adapter = TCPServerAdapter(port)
    threading.Thread(target=adapter.listen, args=(callback,), daemon=True).start()

    for _ in range(50):
        try:
            conn = socket.create_connection(("127.0.0.1", port), timeout=1)
            break
        except ConnectionRefusedError:
            threading.Event().wait(0.05)
    with conn:
        conn.sendall(b'{"id": "A", "pr')
        conn.sendall(b'ice": 1}\n\n{"id": "B", "price": 2}\n')

    assert listo.wait(5)
    assert recibidos == [{"id": "A", "price": 1}, {"id": "B", "price": 2}]


def test_listener_procesa_mensaje_y_tolera_json_invalido(app, monkeypatch):
    monkeypatch.setenv("MIDDLEWARE_TYPE", "tcp_server")
    listener = TicketSocketListener()
    listener.app = app

    listener.process_message(b'{"id": "EXT-7", "price": 500, "event": "Teatro", "rut": 44444444}')
    listener.process_message(b"esto no es json")

    assert [t.external_id for t in Ticket.query.all()] == ["EXT-7"]


def test_notification_client_envia_json_por_tcp(monkeypatch):
    port = _puerto_libre()
    srv = socket.socket()
    srv.bind(("127.0.0.1", port))
    srv.listen()
    monkeypatch.setenv("MIDDLEWARE_NOTIFY_HOST", "127.0.0.1")
    monkeypatch.setenv("MIDDLEWARE_NOTIFY_PORT", str(port))

    NotificationClient._send_internal({"type": "TICKET_PAID", "data": {"external_id": "X"}})

    srv.settimeout(5)
    conn, _ = srv.accept()
    with conn, srv:
        data = conn.recv(4096)
    assert data.endswith(b"\n")
    assert json.loads(data)["type"] == "TICKET_PAID"


def test_notification_client_no_lanza_si_middleware_caido(monkeypatch):
    monkeypatch.setenv("MIDDLEWARE_NOTIFY_HOST", "127.0.0.1")
    monkeypatch.setenv("MIDDLEWARE_NOTIFY_PORT", str(_puerto_libre()))
    NotificationClient._send_internal({"type": "X", "data": {}})
