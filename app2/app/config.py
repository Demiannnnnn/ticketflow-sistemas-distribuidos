import os

class Config:
    SECRET_KEY = os.environ.get('APP2_SECRET_KEY', 'dev-secret-key-ticketflow-app2-secure-2026')
    
    db_user = os.environ.get('APP2_DB_USER')
    db_password = os.environ.get('APP2_DB_PASSWORD')
    db_host = os.environ.get('APP2_DB_HOST')
    db_port = os.environ.get('APP2_DB_PORT', '3306')
    db_name = os.environ.get('APP2_DB_NAME')
    
    if db_user and db_password and db_host and db_name:
        SQLALCHEMY_DATABASE_URI = f"mysql+mysqlconnector://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    else:
        # Fallback
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///app2_dev.db')

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True
    }


