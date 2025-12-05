from datetime import datetime
import enum
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Nullable
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class TicketStatus(enum.Enum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAID = "PAID"
    USED = "USED"
    REFUNDED = "REFUNDED"


class User(db.Model):
    __tablename__ = "users"
    rut = db.Column(db.Integer, primary_key=True, autoincrement=False)
    full_name = db.Column(db.String(128), nullable=False, default="Usuario Pendiente")
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)

    # Relación con Tickets
    tickets = db.relationship("Ticket", backref="user", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Ticket(db.Model):
    __tablename__ = "tickets"
    id = db.Column(db.Integer, primary_key=True)
    seat_id = db.Column(db.String(64), nullable=False)
    event_id = db.Column(db.String(64), Nullable=False)
    price = db.Column(db.Float, nullable=False)
    event_name = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    status = db.Column(db.Enum(TicketStatus), default=TicketStatus.PENDING_PAYMENT)

    user_rut = db.Column(db.Integer, db.ForeignKey("users.rut"), nullable=False)

    # Relación con Payment (0..1)
    payment = db.relationship("Payment", backref="ticket", uselist=False, lazy=True)


class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    paid_at = db.Column(db.DateTime, default=datetime.utcnow)
    payment_method = db.Column(db.String(50))

    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False)
