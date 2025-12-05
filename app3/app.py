import os
import requests
import json
import pymysql
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt

app = Flask(__name__)
app.config['SECRET_KEY'] = 'un-secret-muy-secreto'

# ========================================
# DB CONFIG
# ========================================
db_host = os.environ.get('APP3_DB_HOST')
db_user = os.environ.get('APP3_DB_USER')
db_password = os.environ.get('APP3_DB_PASSWORD')
db_name = os.environ.get('APP3_DB_NAME')

def get_db_connection():
    return pymysql.connect(host=db_host,
                             user=db_user,
                             password=db_password,
                             database=db_name,
                             cursorclass=pymysql.cursors.DictCursor)

# ========================================
# LOGIN & BCRYPT
# ========================================
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

class User(UserMixin):
    def __init__(self, id, full_name, email, password_hash):
        self.id = id
        self.full_name = full_name
        self.email = email
        self.password_hash = password_hash

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE rut = %s", (user_id,))
        user_data = cursor.fetchone()
    conn.close()
    if user_data:
        return User(id=user_data['rut'], full_name=user_data['full_name'], email=user_data['email'], password_hash=user_data['password_hash'])
    return None

# URLs de servicios
APP1_API_URL = "http://nginx/api/events"
APP1_RESERVE_URL = "http://nginx/api/reserve"
MIDDLEWARE_URL = "http://middleware:8000/order"

@app.route('/')
def index():
    """
    Renderiza la página principal con la lista de eventos de App1.
    """
    events = []
    error_message = None
    try:
        response = requests.get(APP1_API_URL, timeout=5)
        response.raise_for_status()
        data = response.json()
        events = data.get('events', [])
    except requests.exceptions.RequestException as e:
        print(f"Error al conectar con App1: {e}")
        error_message = "No se pudo cargar la lista de eventos. El servicio de App1 podría no estar disponible."
    
    return render_template('index.html', events=events, error_message=error_message)

@app.route('/evento/<int:event_id>/asientos')
@login_required
def ver_asientos(event_id):
    """
    Muestra los asientos para un evento específico.
    """
    event = None
    seats = []
    error_message = None
    
    try:
        all_events_response = requests.get(APP1_API_URL, timeout=5)
        all_events_response.raise_for_status()
        all_events = all_events_response.json().get('events', [])
        for e in all_events:
            if e.get('id') == event_id:
                event = e
                break
        
        if not event:
            error_message = "El evento especificado no fue encontrado."
        else:
            seats_response = requests.get(f"http://nginx/api/events/{event_id}/seats", timeout=5)
            seats_response.raise_for_status()
            seats = seats_response.json().get('seats', [])

    except requests.exceptions.RequestException as e:
        print(f"Error al conectar con App1 para obtener asientos: {e}")
        error_message = "No se pudo cargar la información de los asientos."

    return render_template('seats.html', event=event, seats=seats, error_message=error_message)

@app.route('/reservar_asiento', methods=['POST'])
@login_required
def reservar_asiento():
    """
    Endpoint para reservar un asiento.
    1. Llama a App1 para reservar el asiento.
    2. Si tiene éxito, llama al Middleware para encolar la facturación.
    """
    data = request.get_json()
    seat_id = data.get('seat_id')
    user_id = current_user.id
    event_id = data.get('event_id')

    # Paso 1: Intentar reservar el asiento en App1
    try:
        reserve_payload = {'seat_id': seat_id, 'user_id': user_id}
        response_app1 = requests.post(APP1_RESERVE_URL, json=reserve_payload, timeout=5)

        if response_app1.status_code != 200:
            # Si App1 falla la reserva (ej: asiento ocupado), retornar el error.
            error_details = response_app1.json().get('error', 'Error desconocido en App1')
            return jsonify({'error': f"App1 no pudo reservar el asiento: {error_details}"}), response_app1.status_code

    except requests.exceptions.RequestException as e:
        print(f"Error de conexión con App1 al reservar: {e}")
        return jsonify({'error': 'No se pudo conectar con el servicio de reservas (App1)'}), 503

    # Paso 2: Si la reserva en App1 tuvo éxito, enviar al Middleware
    try:
        middleware_payload = {
            'event_id': str(event_id), 
            'user_id': str(user_id), 
            'quantity': 1
        }
        response_middleware = requests.post(MIDDLEWARE_URL, json=middleware_payload, timeout=5)
        response_middleware.raise_for_status()

    except requests.exceptions.RequestException as e:
        # Aquí estamos en un estado inconsistente: el asiento se reservó en App1,
        # pero no se pudo enviar a facturación. En un sistema real, se necesitaría
        # un mecanismo de compensación o reintento.
        print(f"¡INCONSISTENCIA! Asiento {seat_id} reservado pero no se pudo encolar para facturación: {e}")
        return jsonify({
            'message': '¡Asiento reservado! Pero hubo un problema al generar tu factura. Contacta a soporte.'
        }), 200 # Aún así damos éxito al usuario, ya que tiene su asiento.

    # Si todo fue bien:
    return jsonify({
        'message': '¡Reserva y orden de facturación procesadas exitosamente!'
    }), 200

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('profile'))
    if request.method == 'POST':
        rut = request.form.get('rut')
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            try:
                cursor.execute("INSERT INTO users (rut, full_name, email, password_hash) VALUES (%s, %s, %s, %s)", 
                               (rut, full_name, email, hashed_password))
                conn.commit()
                flash('Tu cuenta ha sido creada! Ya puedes iniciar sesión.', 'success')
                return redirect(url_for('login'))
            except pymysql.err.IntegrityError:
                flash('El RUT o email ya existen.', 'danger')
        conn.close()
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('profile'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = load_user_by_email(email)

        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('profile'))
        else:
            flash('Inicio de sesión fallido. Por favor, revisa tu email y contraseña.', 'danger')
            
    return render_template('login.html')

def load_user_by_email(email):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user_data = cursor.fetchone()
    conn.close()
    if user_data:
        return User(id=user_data['rut'], full_name=user_data['full_name'], email=user_data['email'], password_hash=user_data['password_hash'])
    return None

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
