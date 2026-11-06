from app.models import TicketStatus


def registrar(client, **over):
    data = {"email": "ana@test.cl", "rut": "12345678", "full_name": "Ana", "password": "clave"}
    data.update(over)
    return client.post("/register", data=data)


def login(client, email="ana@test.cl", password="clave"):
    return client.post("/login", data={"email": email, "password": password})


def test_raiz_sin_sesion_redirige_a_login(client):
    r = client.get("/")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/login")


def test_registro_valida_campos_y_rut_numerico(client):
    assert b"Missing data" in registrar(client, email="").data
    assert b"RUT must be a number" in registrar(client, rut="12.345.678-5").data


def test_registro_login_y_mis_tickets(client, crear_ticket):
    crear_ticket(rut=12345678)
    r = registrar(client)
    assert r.status_code == 302 and r.headers["Location"].endswith("/login")

    r = login(client)
    assert r.status_code == 302 and r.headers["Location"].endswith("/my-tickets")

    r = client.get("/my-tickets")
    assert r.status_code == 200
    assert b"Concierto" in r.data


def test_login_invalido(client):
    registrar(client)
    r = login(client, password="mala")
    assert r.status_code == 200
    assert b"Invalid credentials" in r.data


def test_rutas_protegidas_redirigen_sin_sesion(client):
    for path in ["/my-tickets", "/payment/1", "/view-qr/1"]:
        r = client.get(path)
        assert r.status_code == 302, path
        assert r.headers["Location"].endswith("/login"), path
    for path in ["/pay-ticket/1", "/refund-ticket/1", "/use-ticket/1"]:
        assert client.post(path).status_code == 302, path


def test_pagar_usar_por_http(client, crear_ticket):
    t = crear_ticket(rut=12345678)
    registrar(client)
    login(client)

    assert client.get(f"/payment/{t.id}").status_code == 200
    assert client.post(f"/pay-ticket/{t.id}").status_code == 302
    assert t.status == TicketStatus.PAID

    assert client.get(f"/view-qr/{t.id}").status_code == 200
    client.post(f"/use-ticket/{t.id}")
    assert t.status == TicketStatus.USED


def test_ticket_ajeno_no_se_muestra(client, crear_ticket):
    ajeno = crear_ticket(rut=99999999)
    registrar(client)
    login(client)
    r = client.get(f"/payment/{ajeno.id}")
    assert r.status_code == 302 and r.headers["Location"].endswith("/my-tickets")


def test_logout_cierra_sesion(client):
    registrar(client)
    login(client)
    client.get("/logout")
    assert client.get("/my-tickets").status_code == 302
