from flask import Flask
from config import Config
# Extensions can be initialized here, for example:
# from flask_sqlalchemy import SQLAlchemy

# db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # db.init_app(app)

    with app.app_context():
        from . import routes
        # In a real scenario, you would initialize the consumer here
        # from . import consumer
        # consumer.start_consuming()

    return app
