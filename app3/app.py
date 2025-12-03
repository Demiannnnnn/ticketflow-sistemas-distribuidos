import os
import requests
import json
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

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
def reservar_asiento():
    """
    Endpoint para reservar un asiento.
    1. Llama a App1 para reservar el asiento.
    2. Si tiene éxito, llama al Middleware para encolar la facturación.
    """
    data = request.get_json()
    seat_id = data.get('seat_id')
    user_id = data.get('user_id')
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
