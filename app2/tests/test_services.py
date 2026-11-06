from app.models import User, Ticket, Payment, TicketStatus
from app.services import AuthService, TicketService


class TestAuthService:
    def test_registro_y_login(self, db):
        user = AuthService.register(12345678, "ana@test.cl", "Ana", "clave-segura")
        assert user is not None
        assert user.password_hash != "clave-segura"

        assert AuthService.login("ana@test.cl", "clave-segura").rut == 12345678
        assert AuthService.login("ana@test.cl", "otra") is None
        assert AuthService.login("nadie@test.cl", "clave-segura") is None

    def test_no_permite_rut_ya_registrado(self, db):
        AuthService.register(12345678, "ana@test.cl", "Ana", "clave")
        assert AuthService.register(12345678, "otra@test.cl", "Otra", "clave") is None

    def test_no_permite_email_de_otro_usuario(self, db):
        AuthService.register(12345678, "ana@test.cl", "Ana", "clave")
        assert AuthService.register(87654321, "ana@test.cl", "Impostor", "clave") is None

    def test_registro_activa_usuario_placeholder_y_hereda_sus_tickets(self, db, crear_ticket):
        crear_ticket(rut=22222222)
        placeholder = db.session.get(User, 22222222)
        assert placeholder.password_hash is None

        # Un placeholder no puede iniciar sesión
        assert AuthService.login(None, "x") is None

        user = AuthService.register(22222222, "beto@test.cl", "Beto", "clave")
        assert user.rut == 22222222
        assert user.full_name == "Beto"
        assert len(user.tickets) == 1
        assert AuthService.login("beto@test.cl", "clave").rut == 22222222

    def test_activar_placeholder_con_email_ajeno_no_rompe(self, db, crear_ticket):
        AuthService.register(12345678, "ana@test.cl", "Ana", "clave")
        crear_ticket(rut=22222222)

        assert AuthService.register(22222222, "ana@test.cl", "Beto", "clave") is None
        assert db.session.get(User, 22222222).password_hash is None


class TestRecepcionDeTickets:
    def test_crea_ticket_pendiente_y_usuario_placeholder(self, db):
        t = TicketService.receive_external_ticket({"id": "EXT-9", "price": "9990", "event": "Jazz", "rut": 33333333})

        assert t.status == TicketStatus.PENDING_PAYMENT
        assert t.price == 9990.0
        assert t.event_name == "Jazz"
        assert db.session.get(User, 33333333).full_name == "Usuario Pendiente"

    def test_es_idempotente_por_external_id(self, db):
        datos = {"id": "EXT-9", "price": 100, "rut": 33333333}
        a = TicketService.receive_external_ticket(datos)
        b = TicketService.receive_external_ticket(datos)
        assert a.id == b.id
        assert Ticket.query.count() == 1

    def test_evento_por_defecto_y_rut_obligatorio(self, db):
        t = TicketService.receive_external_ticket({"id": "EXT-1", "price": 1, "rut": 1})
        assert t.event_name == "Unknown Event"
        assert TicketService.receive_external_ticket({"id": "EXT-2", "price": 1}) is None
        assert Ticket.query.count() == 1


class TestCicloDeVidaDelTicket:
    def test_pago_registra_payment_y_notifica(self, db, crear_ticket, notificaciones):
        t = crear_ticket(price=15000.0)

        assert TicketService.process_payment(11111111, t.id) is True
        assert t.status == TicketStatus.PAID
        pago = Payment.query.filter_by(ticket_id=t.id).one()
        assert pago.amount == 15000.0
        assert pago.payment_method == "credit_card"
        assert notificaciones == [("TICKET_PAID", {"external_id": "EXT-1", "price": 15000.0, "user_rut": 11111111})]

    def test_no_se_paga_dos_veces(self, db, crear_ticket):
        t = crear_ticket()
        assert TicketService.process_payment(11111111, t.id)
        assert TicketService.process_payment(11111111, t.id) is False
        assert Payment.query.count() == 1

    def test_solo_el_dueno_opera_su_ticket(self, db, crear_ticket):
        t = crear_ticket(rut=11111111)
        assert TicketService.process_payment(99999999, t.id) is False
        assert TicketService.get_ticket(99999999, t.id) is None
        assert t.status == TicketStatus.PENDING_PAYMENT

    def test_usar_requiere_ticket_pagado(self, db, crear_ticket):
        t = crear_ticket()
        assert TicketService.use_ticket(11111111, t.id) is False
        TicketService.process_payment(11111111, t.id)
        assert TicketService.use_ticket(11111111, t.id) is True
        assert t.status == TicketStatus.USED
        assert TicketService.use_ticket(11111111, t.id) is False

    def test_devolucion_solo_de_ticket_pagado_y_no_usado(self, db, crear_ticket, notificaciones):
        pendiente = crear_ticket(external_id="P")
        assert TicketService.refund_ticket(11111111, pendiente.id) is False

        pagado = crear_ticket(external_id="A")
        TicketService.process_payment(11111111, pagado.id)
        assert TicketService.refund_ticket(11111111, pagado.id) is True
        assert pagado.status == TicketStatus.REFUNDED
        assert notificaciones[-1] == ("TICKET_REFUNDED", {"external_id": "A", "user_rut": 11111111})
        assert TicketService.refund_ticket(11111111, pagado.id) is False

        usado = crear_ticket(external_id="U")
        TicketService.process_payment(11111111, usado.id)
        TicketService.use_ticket(11111111, usado.id)
        assert TicketService.refund_ticket(11111111, usado.id) is False

    def test_operaciones_sobre_ticket_inexistente(self, db):
        assert TicketService.process_payment(1, 999) is False
        assert TicketService.use_ticket(1, 999) is False
        assert TicketService.refund_ticket(1, 999) is False

    def test_listado_por_usuario(self, db, crear_ticket):
        crear_ticket(rut=1, external_id="A")
        crear_ticket(rut=1, external_id="B")
        crear_ticket(rut=2, external_id="C")
        assert sorted(t.external_id for t in TicketService.get_user_tickets(1)) == ["A", "B"]
