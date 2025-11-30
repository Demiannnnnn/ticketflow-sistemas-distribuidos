from flask import Flask
from .config import Config
from .models import db

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    from .routes import auth_bp, ticket_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(ticket_bp)

    with app.app_context():
        # Retry logic for DB connection
        import time
        from sqlalchemy.exc import OperationalError
        
        retries = 10
        while retries > 0:
            try:
                db.create_all()
                print("Database connection successful and tables created.")
                break
            except OperationalError as e:
                retries -= 1
                print(f"Database not ready yet, retrying in 5 seconds... ({retries} retries left)")
                time.sleep(5)
                if retries == 0:
                    print("Could not connect to database after multiple attempts.")
                    raise e

    return app
