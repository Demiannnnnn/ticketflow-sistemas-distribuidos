
import sys
import os
import unittest
from app import create_app, db
from app.models import User, Ticket, TicketStatus, Payment
from app.services import AuthService, TicketService

class TestSequenceCompliance(unittest.TestCase):
    def setUp(self):
        # Ensure we are in testing mode so we don't break prod data if possible, 
        # though here we want to test against the running container DB.
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app_context = self.app.app_context()
        self.app_context.push()
        # create_app already calls db.create_all(), but for tests we might want to ensure it.
        # If we want to start fresh every time:
        # db.drop_all() 
        # db.create_all()
        # For now, we rely on the app's startup logic or the container's init.sql.

    def tearDown(self):
        db.session.remove()
        # db.drop_all() # WARNING: This wipes the shared container DB. 
        # Uncomment if you want a clean slate after every test, but might annoy the user if they want to inspect data.
        # Let's keep it commented out or removed for now to persist state, 
        # OR if we want a self-contained test, we drop. 
        # Given the user instruction to "verify", usually we want clean state. 
        # But I will comment it out to be safe and just remove the session.
        self.app_context.pop()

    def test_full_user_flow(self):
        print("\n--- Testing Placeholder User and Registration Sequence ---")
        
        # 1. Receive Ticket for UNKNOWN RUT (Should create placeholder)
        target_rut = 12345678
        ticket_data = {
            "id": "EXT999",
            "price": 150.0,
            "event": "Future Event",
            "rut": target_rut
        }
        
        print(f"Receiving ticket for non-existent RUT: {target_rut}")
        ticket = TicketService.receive_external_ticket(ticket_data)
        
        self.assertIsNotNone(ticket)
        self.assertEqual(ticket.user_rut, target_rut)
        
        # Check User is Placeholder
        user = User.query.get(target_rut)
        self.assertIsNotNone(user)
        self.assertIsNone(user.password_hash)
        self.assertIsNone(user.email)
        self.assertEqual(user.full_name, "Usuario Pendiente")
        print("Placeholder user created successfully.")

        # 2. Register User with SAME RUT (Should update placeholder)
        email = "realuser@example.com"
        full_name = "Juan Perez"
        password = "realpassword"
        
        print(f"Registering real user with RUT: {target_rut}")
        registered_user = AuthService.register(target_rut, email, full_name, password)
        
        self.assertIsNotNone(registered_user)
        self.assertEqual(registered_user.rut, target_rut)
        self.assertEqual(registered_user.email, email)
        self.assertEqual(registered_user.full_name, full_name)
        self.assertIsNotNone(registered_user.password_hash)
        print("User registered and placeholder updated.")
        
        # 3. Verify Login
        print("Attempting login...")
        logged_in_user = AuthService.login(email, password)
        self.assertIsNotNone(logged_in_user)
        self.assertEqual(logged_in_user.rut, target_rut)
        print("Login successful.")
        
        # 4. Verify Ticket Ownership
        user_tickets = TicketService.get_user_tickets(target_rut)
        self.assertEqual(len(user_tickets), 1)
        self.assertEqual(user_tickets[0].external_id, "EXT999")
        print("Ticket ownership verified.")

if __name__ == '__main__':
    unittest.main()
