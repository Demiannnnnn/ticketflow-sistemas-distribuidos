-- Crear la base de datos si no existe
CREATE DATABASE IF NOT EXISTS app3_db;
USE app3_db;

-- Tabla de Usuarios
CREATE TABLE IF NOT EXISTS users (
    rut INT PRIMARY KEY, -- RUT manual, sin auto_increment
    full_name VARCHAR(128) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
