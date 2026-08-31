-- Crear la base de datos si no existe
CREATE DATABASE IF NOT EXISTS invoicing;
USE invoicing;

-- Definir el ENUM para el estado del ticket
-- En MariaDB/MySQL los ENUMs se definen en la columna, pero aquí seguimos la lógica del diseño.

-- Tabla de Usuarios
CREATE TABLE IF NOT EXISTS users (
    rut INT PRIMARY KEY, -- RUT manual, sin auto_increment
    full_name VARCHAR(128) NOT NULL DEFAULT 'Usuario Pendiente',
    email VARCHAR(120) UNIQUE, -- Puede ser NULL para placeholders
    password_hash VARCHAR(255), -- Puede ser NULL para placeholders
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Tickets
CREATE TABLE IF NOT EXISTS tickets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    external_id VARCHAR(64) NOT NULL UNIQUE COMMENT 'Identificador del Middleware',
    price FLOAT NOT NULL,
    event_name VARCHAR(128) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    status ENUM('PENDING_PAYMENT', 'PAID', 'USED', 'REFUNDED') DEFAULT 'PENDING_PAYMENT',
    user_rut INT NOT NULL,
    FOREIGN KEY (user_rut) REFERENCES users(rut)
);

-- Tabla de Pagos
CREATE TABLE IF NOT EXISTS payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    amount FLOAT NOT NULL,
    paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    payment_method VARCHAR(50) NOT NULL,
    ticket_id INT UNIQUE NOT NULL, -- Relación 1 a 1
    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);
