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
        # 1. Verificar si el email ya está en uso por otro usuario
        user_with_email = User.query.filter_by(email=email).first()
        if user_with_email and user_with_email.rut != rut:
            return None

        # 2. Verificar si existe por RUT
        existing_user = User.query.filter_by(rut=rut).first()
        
        if existing_user:
            if existing_user.password_hash:
                # Ya está registrado completamente
                return None
            else:
                # Es un usuario Placeholder (creado al recibir una orden previa)
                existing_user.email = email
                existing_user.full_name = full_name
                existing_user.set_password(password)
                try:
                    db.session.commit()
                    return existing_user
                except Exception:
                    db.session.rollback()
                    return None
        
        try:
            new_user = User(rut=rut, email=email, full_name=full_name)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            return new_user
        except Exception:
            db.session.rollback()
            return None

class TicketService:
    @staticmethod
    def receive_external_ticket(json_data):
        # Acepta esquema estandarizado (order_id, event_name, seat_number, user_rut, price)
        # y retrocompatibilidad con esquemas previos (id, event, rut)
        external_id = json_data.get('order_id') or json_data.get('id')
        if not external_id:
            import uuid
            external_id = str(uuid.uuid4())

        price_raw = json_data.get('price', 5000.0)
        try:
            price = float(price_raw)
        except (ValueError, TypeError):
            price = 5000.0

        event_name = json_data.get('event_name') or json_data.get('event', 'Evento Sin Nombre')
        seat_number = json_data.get('seat_number')
        if seat_number and f"Asiento {seat_number}" not in event_name:
            event_name = f"{event_name} (Asiento {seat_number})"

        raw_rut = json_data.get('user_rut') or json_data.get('rut') or json_data.get('user_id')
        if not raw_rut:
            print("Error: Ticket received without RUT or User ID")
            return None

        try:
            if isinstance(raw_rut, str):
                rut_str = raw_rut.split('-')[0] if '-' in raw_rut else raw_rut
                digits = ''.join(filter(str.isdigit, rut_str))
                user_rut = int(digits) if digits else None
            else:
                user_rut = int(raw_rut)
        except (ValueError, TypeError):
            print(f"Error: Invalid RUT format: {raw_rut}")
            return None

        if not user_rut:
            print("Error: Empty RUT parsed")
            return None

        try:
            user = User.query.filter_by(rut=user_rut).first()
            if not user:
                # Crear usuario Placeholder para vincular el ticket pendiente
                user = User(rut=user_rut, full_name="Usuario Pendiente")
                db.session.add(user)
                db.session.commit()

            existing_ticket = Ticket.query.filter_by(external_id=external_id).first()
            if existing_ticket:
                return existing_ticket

            new_ticket = Ticket(
                external_id=external_id,
                price=price,
                event_name=event_name,
                user_rut=user.rut,
                status=TicketStatus.PENDING_PAYMENT
            )
            db.session.add(new_ticket)
            db.session.commit()
            print(f" [✓] Ticket successfully created for RUT {user.rut}: {external_id} - {event_name}")
            return new_ticket
        except Exception as e:
            db.session.rollback()
            print(f"Error saving external ticket: {e}")
            return None

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
