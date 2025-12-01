import os
import pika
import json
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# URLs de servicios
APP1_API_URL = "http://nginx/api/events"

# Configuración de RabbitMQ
RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'localhost')
RABBITMQ_QUEUE = 'orden_creada'

@app.route('/')
def index():
    """
    Renderiza la página principal con la lista de eventos de App1.
    """
    events = []
    error_message = None
    try:
        response = requests.get(APP1_API_URL, timeout=5)
        response.raise_for_status()  # Lanza un error para respuestas 4xx/5xx
        data = response.json()
        events = data.get('events', [])
    except requests.exceptions.RequestException as e:
        print(f"Error al conectar con App1: {e}")
        error_message = "No se pudo cargar la lista de eventos. El servicio de App1 podría no estar disponible."
    
    return render_template('index.html', events=events, error_message=error_message)

@app.route('/comprar', methods=['POST'])
def comprar():
    """
    Endpoint para procesar una compra.
    Publica un mensaje en RabbitMQ con los datos de la compra.
    """
    try:
        # Intenta conectar a RabbitMQ
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()

        # Asegura que la cola existe
        channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)

        # Obtiene los datos de la compra del request (simulados en el frontend)
        datos_compra = request.get_json()
        
        # Publica el mensaje en la cola
        channel.basic_publish(
            exchange='',
            routing_key=RABBITMQ_QUEUE,
            body=json.dumps(datos_compra),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Hace el mensaje persistente
            ))
        
        connection.close()
        
        print(f" [x] Enviado a RabbitMQ: {datos_compra}")
        return jsonify({'mensaje': '¡Compra recibida! Recibirás una confirmación pronto.'}), 200

    except pika.exceptions.AMQPConnectionError as e:
        print(f"Error conectando a RabbitMQ: {e}")
        return jsonify({'mensaje': 'Error: El servicio de procesamiento de órdenes no está disponible.'}), 503 # Service Unavailable
    except Exception as e:
        print(f"Ocurrió un error inesperado: {e}")
        return jsonify({'mensaje': 'Error interno al procesar la solicitud.'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
