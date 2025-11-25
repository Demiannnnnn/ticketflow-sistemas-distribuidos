from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.mysql import JSON

db = SQLAlchemy()

class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, unique=True, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='pending')
    invoice_data = db.Column(JSON)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())
    updated_at = db.Column(db.TIMESTAMP, server_default=db.func.now(), onupdate=db.func.now())
    tickets = db.relationship('Ticket', backref='invoice', lazy=True)

class Ticket(db.Model):
    __tablename__ = 'tickets'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    ticket_path = db.Column(db.String(255))
    status = db.Column(db.String(50), nullable=False, default='pending')
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())
