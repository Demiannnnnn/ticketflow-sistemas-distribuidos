import os
import requests
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User
from services import AuthService

app = Flask(__name__)

# Configuración
app.config['SECRET_KEY'] = 'tu_secreto_muy_seguro' # Cambiar en producción
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{os.environ.get('DB_USER')}:{os.environ.get('DB_PASSWORD')}@{os.environ.get('DB_HOST')}/{os.environ.get('DB_NAME')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar Extensiones
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Crear tablas al inicio (simple workaround para dev)
with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# URLs de servicios
APP1_API_URL = "http://nginx/api/events"
APP1_RESERVE_URL = "http://nginx/api/reserve"
MIDDLEWARE_URL = "http://middleware:8000/order"

# --- Rutas de Autenticación ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        rut = request.form.get('rut')
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = AuthService.register(rut, email, full_name, password)
        if user:
            flash('Registro exitoso. Por favor inicia sesión.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Error: El usuario ya existe o el email está en uso.', 'error')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = AuthService.login(email, password)
        if user:
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Email o contraseña incorrectos.', 'error')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('login'))

# --- Rutas de Negocio ---

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
    """
    data = request.get_json()
    seat_id = data.get('seat_id')
    event_id = data.get('event_id')
    user_id = current_user.rut # Usar el RUT del usuario autenticado

    # Paso 1: Intentar reservar el asiento en App1
    try:
        reserve_payload = {'seat_id': seat_id, 'user_id': user_id}
        response_app1 = requests.post(APP1_RESERVE_URL, json=reserve_payload, timeout=5)

        if response_app1.status_code != 200:
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
            'quantity': 1,
            'seat_id': str(seat_id)
        }
        response_middleware = requests.post(MIDDLEWARE_URL, json=middleware_payload, timeout=5)
        response_middleware.raise_for_status()

    except requests.exceptions.RequestException as e:
        print(f"¡INCONSISTENCIA! Asiento {seat_id} reservado pero no se pudo encolar para facturación: {e}")
        return jsonify({
            'message': '¡Asiento reservado! Pero hubo un problema al generar tu factura. Contacta a soporte.'
        }), 200

    return jsonify({
        'message': '¡Reserva y orden de facturación procesadas exitosamente!'
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)