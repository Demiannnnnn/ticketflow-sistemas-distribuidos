from datetime import datetime
from .models import db, User, Ticket, Payment, TicketStatus

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
        if user and user.check_password(password):
            return user
        return None

    @staticmethod
    def register(email, username, password):
        if User.query.filter_by(email=email).first():
            return None # User already exists
        
        new_user = User(email=email, username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        return new_user

class TicketService:
    @staticmethod
    def receive_external_ticket(json_data):
        # Se asume que json_data trae info del ticket y tal vez del usuario
        # Por simplicidad, si el usuario no existe, se asigna a un usuario default o se crea
        # Aquí asumiremos que 'user_id' viene en el json o similar, o buscaremos por username
        
        external_id = json_data.get('id')
        price = json_data.get('price')
        event_name = json_data.get('event', 'Unknown Event')
        username = json_data.get('username', 'guest') # Simplificación
        
        user = User.query.filter_by(username=username).first()
        if not user:
            # Crear usuario al vuelo si no existe, para que el ticket tenga dueño
            user = AuthService.register(f"{username}@example.com", username, "default123")
        
        existing_ticket = Ticket.query.filter_by(external_id=external_id).first()
        if existing_ticket:
            return existing_ticket
            
        new_ticket = Ticket(
            external_id=external_id,
            price=float(price),
            event_name=event_name,
            user_id=user.id,
            status=TicketStatus.PENDING_PAYMENT
        )
        db.session.add(new_ticket)
        db.session.commit()
        return new_ticket

    @staticmethod
    def process_payment(user_id, ticket_id, payment_token="dummy_token"):
        ticket = Ticket.query.filter_by(id=ticket_id, user_id=user_id).first()
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
            return True
        return False

    @staticmethod
    def use_ticket(user_id, ticket_id):
        ticket = Ticket.query.filter_by(id=ticket_id, user_id=user_id).first()
        if not ticket:
            return False
        
        if ticket.status == TicketStatus.PAID:
            ticket.status = TicketStatus.USED
            db.session.commit()
            return True
        return False

    @staticmethod
    def refund_ticket(user_id, ticket_id):
        ticket = Ticket.query.filter_by(id=ticket_id, user_id=user_id).first()
        if not ticket or not ticket.payment:
            return False
        
        if ticket.status == TicketStatus.PAID:
            # Solo se puede devolver si está pagado y no usado
            if PaymentGateway.refund_transaction(ticket.payment.id):
                ticket.status = TicketStatus.REFUNDED
                db.session.commit()
                return True
        return False

    @staticmethod
    def get_user_tickets(user_id):
        return Ticket.query.filter_by(user_id=user_id).all()
