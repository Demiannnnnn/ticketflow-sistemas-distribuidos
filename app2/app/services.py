from datetime import datetime
from .models import db, User, Ticket, Payment, TicketStatus
from .notification_client import NotificationClient

class PaymentGateway:
    @staticmethod
    def charge_credit_card(amount, token):
        # Simulación de cobro exitoso
        print(f"Charging {amount} with token {token}")
        return True

    @staticmethod
    def refund_transaction(transaction_id):
        # Simulación de reembolso
        print(f"Refunding transaction {transaction_id}")
        return True

class AuthService:
    @staticmethod
    def login(email, password):
        user = User.query.filter_by(email=email).first()
        # Verificar que exista, que tenga password setead (no sea placeholder) y que el password coincida
        if user and user.password_hash and user.check_password(password):
            return user
        return None

    @staticmethod
    def register(rut, email, full_name, password):
        # Verificar si existe por RUT primero
        existing_user = User.query.filter_by(rut=rut).first()
        
        if existing_user:
            if existing_user.password_hash:
                # Ya está registrado completamente
                return None
            else:
                # Es un usuario Placeholder (creado por un ticket previo)
                # Actualizamos sus datos para "activar" la cuenta
                existing_user.email = email
                existing_user.full_name = full_name
                existing_user.set_password(password)
                db.session.commit()
                return existing_user
        
        # Verificar si el email ya está en uso por OTRO usuario (aunque el RUT sea nuevo)
        if User.query.filter_by(email=email).first():
            return None
        
        new_user = User(rut=rut, email=email, full_name=full_name)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        return new_user

class TicketService:
    @staticmethod
    def receive_external_ticket(json_data):
        # Datos esperados: id, price, event, rut (obligatorio ahora)
        external_id = json_data.get('id')
        price = json_data.get('price')
        event_name = json_data.get('event', 'Unknown Event')
        user_rut = json_data.get('rut')
        
        if not user_rut:
            print("Error: Ticket received without RUT")
            return None
        
        user = User.query.filter_by(rut=user_rut).first()
        if not user:
            # Crear usuario Placeholder (sin email/password) para vincular el ticket
            # Cuando el usuario real se registre con este RUT, tomará posesión de estos tickets.
            user = User(rut=user_rut, full_name="Usuario Pendiente")
            db.session.add(user)
            db.session.commit()
        
        existing_ticket = Ticket.query.filter_by(external_id=external_id).first()
        if existing_ticket:
            return existing_ticket
            
        new_ticket = Ticket(
            external_id=external_id,
            price=float(price),
            event_name=event_name,
            user_rut=user.rut,
            status=TicketStatus.PENDING_PAYMENT
        )
        db.session.add(new_ticket)
        db.session.commit()
        return new_ticket

    @staticmethod
    def process_payment(user_rut, ticket_id, payment_token="dummy_token"):
        ticket = Ticket.query.filter_by(id=ticket_id, user_rut=user_rut).first()
        if not ticket:
            return False
        
        if ticket.status != TicketStatus.PENDING_PAYMENT:
            return False # Ya pagado o usado
            
        if PaymentGateway.charge_credit_card(ticket.price, payment_token):
            ticket.status = TicketStatus.PAID
            payment = Payment(
                amount=ticket.price,
                payment_method="credit_card",
                ticket_id=ticket.id
            )
            db.session.add(payment)
            db.session.commit()
            
            # Notify Middleware
            NotificationClient.send_event("TICKET_PAID", {
                "external_id": ticket.external_id,
                "price": ticket.price,
                "user_rut": ticket.user_rut
            })
            
            return True
        return False

    @staticmethod
    def use_ticket(user_rut, ticket_id):
        ticket = Ticket.query.filter_by(id=ticket_id, user_rut=user_rut).first()
        if not ticket:
            return False
        
        if ticket.status == TicketStatus.PAID:
            ticket.status = TicketStatus.USED
            db.session.commit()
            return True
        return False

    @staticmethod
    def refund_ticket(user_rut, ticket_id):
        ticket = Ticket.query.filter_by(id=ticket_id, user_rut=user_rut).first()
        if not ticket or not ticket.payment:
            return False
        
        if ticket.status == TicketStatus.PAID:
            # Solo se puede devolver si está pagado y no usado
            if PaymentGateway.refund_transaction(ticket.payment.id):
                ticket.status = TicketStatus.REFUNDED
                db.session.commit()
                
                # Notify Middleware
                NotificationClient.send_event("TICKET_REFUNDED", {
                    "external_id": ticket.external_id,
                    "user_rut": ticket.user_rut
                })
                
                return True
        return False

    @staticmethod
    def get_user_tickets(user_rut):
        return Ticket.query.filter_by(user_rut=user_rut).all()

    @staticmethod
    def get_ticket(user_rut, ticket_id):
        return Ticket.query.filter_by(id=ticket_id, user_rut=user_rut).first()
