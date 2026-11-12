import pytest

from app import create_app
from app.config import Config
from app.models import db as _db, User, Ticket, TicketStatus


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture
def notificaciones(monkeypatch):
    """Captura las notificaciones al middleware en vez de abrir sockets."""
    enviadas = []
    monkeypatch.setattr(
        "app.services.NotificationClient.send_event",
        lambda tipo, data: enviadas.append((tipo, data)),
    )
    return enviadas


@pytest.fixture
def app(notificaciones):
    app = create_app(TestConfig)
    with app.app_context():
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def db(app):
    return _db


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def crear_ticket(db):
    def _crear(rut=11111111, status=TicketStatus.PENDING_PAYMENT, external_id="EXT-1", price=15000.0):
        if not db.session.get(User, rut):
            db.session.add(User(rut=rut, full_name="Usuario Pendiente"))
        t = Ticket(external_id=external_id, price=price, event_name="Concierto", user_rut=rut, status=status)
        db.session.add(t)
        db.session.commit()
        return t

    return _crear
