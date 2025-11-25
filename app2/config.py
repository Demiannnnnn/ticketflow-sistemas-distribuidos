import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-secret-key'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'mysql+mysqlconnector://user:password@mariadb/***REMOVED***'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    RABBITMQ_URL = os.environ.get('RABBITMQ_URL') or 'amqp://guest:guest@middleware:5672/'
