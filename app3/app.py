import os
import uuid
from datetime import datetime, timezone
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# URLs de servicios externalizadas con variables de entorno
APP1_API_URL = os.environ.get('APP1_API_URL', 'http://nginx/api/events')
APP1_RESERVE_URL = os.environ.get('APP1_RESERVE_URL', 'http://nginx/api/reserve')
MIDDLEWARE_URL = os.environ.get('MIDDLEWARE_URL', 'http://middleware:8000/order')

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "service": "app3"}), 200

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
        error_message = "No se pudo cargar la lista de eventos. El servicio de reservas (App1) podría no estar disponible."
    
    return render_template('index.html', events=events, error_message=error_message)

@app.route('/evento/<int:event_id>/asientos')
def ver_asientos(event_id):
    """
    Muestra los asientos para un evento específico usando endpoints directos.
    """
    event = None
    seats = []
    error_message = None
    
    try:
        # Intento de consulta directa del evento específico
        event_resp = requests.get(f"{APP1_API_URL}/{event_id}", timeout=5)
        if event_resp.status_code == 200:
            event = event_resp.json().get('event')
        else:
            # Fallback buscando en la lista general de eventos
            all_events_response = requests.get(APP1_API_URL, timeout=5)
            all_events_response.raise_for_status()
            for e in all_events_response.json().get('events', []):
                if e.get('id') == event_id:
                    event = e
                    break
        
        if not event:
            error_message = "El evento especificado no fue encontrado."
        else:
            seats_response = requests.get(f"{APP1_API_URL}/{event_id}/seats", timeout=5)
            seats_response.raise_for_status()
            seats = seats_response.json().get('seats', [])

    except requests.exceptions.RequestException as e:
        print(f"Error al conectar con App1 para obtener asientos: {e}")
        error_message = "No se pudo cargar la información de los asientos desde el gestor de reservas."

    return render_template('seats.html', event=event, seats=seats, error_message=error_message)

@app.route('/reservar_asiento', methods=['POST'])
def reservar_asiento():
    """
    Endpoint para reservar un asiento con Saga / Compensación Distribuida:
    1. Llama a App1 para reservar el asiento (bloqueo transaccional).
    2. Si tiene éxito, llama al Middleware para encolar la orden hacia App2.
    3. Si el Middleware falla, ejecuta COMPENSACIÓN cancelando la reserva en App1 y retorna error.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Cuerpo de solicitud JSON requerido'}), 400

    seat_id = data.get('seat_id')
    event_id = data.get('event_id')
    event_name = data.get('event_name', f'Evento #{event_id}')
    seat_number = data.get('seat_number', str(seat_id))
    raw_rut = data.get('user_rut') or data.get('user_id')
    price = data.get('price', 5000.0)

    if not seat_id or not event_id:
        return jsonify({'error': 'seat_id y event_id son obligatorios'}), 400

    if not raw_rut:
        return jsonify({'error': 'Debe proporcionar un RUT de usuario válido'}), 400

    # Limpiar y validar RUT a formato numérico
    try:
        if isinstance(raw_rut, str):
            digits = ''.join(filter(str.isdigit, raw_rut))
            user_rut = int(digits) if digits else None
        else:
            user_rut = int(raw_rut)
    except (ValueError, TypeError):
        return jsonify({'error': 'Formato de RUT inválido'}), 400

    if not user_rut:
        return jsonify({'error': 'RUT numérico no puede ser vacío o cero'}), 400

    # Paso 1: Intentar reservar el asiento en App1
    try:
        reserve_payload = {'seat_id': seat_id, 'user_id': user_rut}
        response_app1 = requests.post(APP1_RESERVE_URL, json=reserve_payload, timeout=5)

        if response_app1.status_code != 200:
            error_details = 'Error desconocido en App1'
            try:
                error_details = response_app1.json().get('error', error_details)
            except Exception:
                pass
            return jsonify({'error': f"No se pudo reservar el asiento: {error_details}"}), response_app1.status_code

    except requests.exceptions.RequestException as e:
        print(f"Error de conexión con App1 al reservar: {e}")
        return jsonify({'error': 'No se pudo conectar con el servicio de reservas (App1)'}), 503

    # Paso 2: Si la reserva en App1 tuvo éxito, enviar al Middleware con el contrato DTO unificado
    order_id = str(uuid.uuid4())
    middleware_payload = {
        'order_id': order_id,
        'event_id': int(event_id),
        'event_name': str(event_name),
        'seat_id': int(seat_id),
        'seat_number': str(seat_number),
        'user_rut': int(user_rut),
        'price': float(price),
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

    try:
        response_middleware = requests.post(MIDDLEWARE_URL, json=middleware_payload, timeout=5)
        response_middleware.raise_for_status()

    except requests.exceptions.RequestException as e:
        # COMPENSACIÓN (Saga Rollback): El middleware falló, liberamos el asiento en App1
        print(f"[SAGA COMPENSACIÓN] Falló envío a Middleware para orden {order_id}. Cancelando reserva de asiento {seat_id}: {e}")
        try:
            cancel_url = f"{APP1_RESERVE_URL}/{seat_id}/cancel"
            rollback_resp = requests.post(cancel_url, timeout=5)
            print(f"[SAGA COMPENSACIÓN] Resultado cancelación asiento {seat_id}: status {rollback_resp.status_code}")
        except Exception as rollback_err:
            print(f"[SAGA COMPENSACIÓN ERROR] No se pudo cancelar el asiento {seat_id} tras fallo de middleware: {rollback_err}")

        return jsonify({
            'error': 'No se pudo generar la orden de facturación en el sistema. La reserva del asiento ha sido cancelada para evitar cobros indebidos. Por favor intente nuevamente.'
        }), 502

    # Éxito completo del flujo
    return jsonify({
        'message': '¡Reserva y orden de facturación procesadas exitosamente!',
        'order_id': order_id,
        'seat_id': seat_id,
        'user_rut': user_rut
    }), 200


if __name__ == '__main__':
    port = int(os.environ.get('APP3_PORT', 5000))
    app.run(host='0.0.0.0', port=port)

