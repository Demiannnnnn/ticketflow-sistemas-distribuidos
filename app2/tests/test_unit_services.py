import unittest
from app import create_app, db
from app.config import Config
from app.models import User, Ticket, TicketStatus, Payment
from app.services import AuthService, TicketService

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class TestApp2Services(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_standard_dto_external_ticket(self):
        # Probar DTO unificado estandarizado
        dto = {
            "order_id": "test-uuid-12345",
            "event_id": 1,
            "event_name": "Concierto Rock Nacional",
            "seat_id": 10,
            "seat_number": "A-10",
            "user_rut": "12.345.678-9",
            "price": 7500.0,
            "timestamp": "2026-08-30T22:00:00Z"
        }
        ticket = TicketService.receive_external_ticket(dto)
        self.assertIsNotNone(ticket)
        self.assertEqual(ticket.external_id, "test-uuid-12345")
        self.assertEqual(ticket.user_rut, 12345678)
        self.assertEqual(ticket.price, 7500.0)
        self.assertIn("A-10", ticket.event_name)
        self.assertEqual(ticket.status, TicketStatus.PENDING_PAYMENT)

        # Verificar creación de placeholder user
        user = User.query.get(12345678)
        self.assertIsNotNone(user)
        self.assertEqual(user.full_name, "Usuario Pendiente")

        # Registro posterior del usuario real
        reg_user = AuthService.register(12345678, "juan@example.com", "Juan Pérez", "pass1234")
        self.assertIsNotNone(reg_user)
        self.assertEqual(reg_user.email, "juan@example.com")
        self.assertEqual(reg_user.full_name, "Juan Pérez")

        # Pago de ticket
        paid = TicketService.process_payment(12345678, ticket.id)
        self.assertTrue(paid)
        self.assertEqual(ticket.status, TicketStatus.PAID)

        # Uso de ticket
        used = TicketService.use_ticket(12345678, ticket.id)
        self.assertTrue(used)
        self.assertEqual(ticket.status, TicketStatus.USED)

if __name__ == '__main__':
    unittest.main()
