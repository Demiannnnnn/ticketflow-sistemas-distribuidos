from app import create_app
from app.rabbitmq_consumer import RabbitMQConsumer

app = create_app()
consumer = RabbitMQConsumer()

if __name__ == '__main__':
    print("Starting RabbitMQ Consumer...")
    consumer.start(app)
