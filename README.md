# Sistema de Venta de Tickets (App2)

Este proyecto implementa la **App2 (Ticketera)**, un componente central en una arquitectura de sistemas distribuidos para la gestión, venta y validación de entradas a eventos. El sistema está diseñado para integrarse con un **Middleware** externo mediante mensajería asíncrona (RabbitMQ) y ofrece una interfaz web para los usuarios finales.

## 📋 Tabla de Contenidos
1. [Características Principales](#-características-principales)
2. [Arquitectura del Sistema](#-arquitectura-del-sistema)
3. [Estructura de Datos](#-estructura-de-datos)
4. [Integración Middleware (Socket/Cola)](#-integración-middleware)
5. [Instalación y Ejecución](#-instalación-y-ejecución)
6. [Diagramas](#-diagramas)

---

## 🚀 Características Principales

*   **Recepción Asíncrona de Tickets:** Escucha activa de una cola RabbitMQ para recibir tickets generados externamente.
*   **Gestión de Usuarios Híbrida:**
    *   **Registro Completo:** Usuarios con RUT, Nombre, Email y Contraseña.
    *   **Usuarios Placeholder:** Creación automática de perfiles temporales (solo RUT) cuando llega un ticket para un usuario no registrado.
    *   **Vinculación Automática:** Al registrarse un usuario real, "hereda" automáticamente todos los tickets que estaban asociados a su RUT.
*   **Flujo de Compra:**
    *   Estado inicial: `PENDING_PAYMENT`.
    *   Simulación de Pasarela de Pago (integración stub).
    *   Transición a `PAID`.
*   **Uso de Tickets:** Validación y "quemado" de entradas (Check-in), cambiando estado a `USED`.
*   **Reembolsos:** Lógica de negocio para devoluciones (solo tickets pagados y no usados).

---

## 🏗 Arquitectura del Sistema

El proyecto sigue una arquitectura por capas (MVC / Services) implementada en **Python (Flask)** y dockerizada para facilitar el despliegue.

*   **Frontend:** Templates Jinja2 + Bootstrap (HTML/CSS).
*   **Backend API:** Flask Routes (`routes.py`).
*   **Lógica de Negocio:** Capa de Servicios (`services.py`) que desacopla la lógica de las rutas.
*   **Persistencia:** MariaDB (MySQL) con SQLAlchemy ORM.
*   **Mensajería:** Cliente Pika para RabbitMQ (`socket_listener.py`).

### Estructura del Proyecto
```
/app2
  ├── app/
  │   ├── models.py       # Modelos de Datos (User, Ticket, Payment)
  │   ├── services.py     # Lógica: AuthService, TicketService
  │   ├── routes.py       # Controladores Web y Endpoints
  │   └── socket_listener.py # Consumidor de RabbitMQ
  ├── run.py              # Entrypoint Web
  ├── run_listener.py     # Entrypoint Listener
  └── start.sh            # Script de arranque Docker
```

---

## 💾 Estructura de Datos

### Entidad: Usuario (`User`)
Identifica a los clientes. El **RUT** es la clave primaria, permitiendo identificar usuarios incluso antes de que se registren formalmente.

| Campo | Tipo | Descripción |
| :--- | :--- | :--- |
| `rut` | INT (PK) | Identificador único nacional (sin DV). |
| `full_name` | VARCHAR | Nombre completo. |
| `email` | VARCHAR | Único. Puede ser `NULL` (Placeholder). |
| `password_hash` | VARCHAR | Hash seguro. Puede ser `NULL` (Placeholder). |

### Entidad: Ticket (`Ticket`)
Representa una entrada a un evento.

| Campo | Tipo | Descripción |
| :--- | :--- | :--- |
| `id` | INT (PK) | ID interno. |
| `external_id` | VARCHAR | ID proveniente del Middleware. |
| `status` | ENUM | `PENDING_PAYMENT`, `PAID`, `USED`, `REFUNDED`. |
| `user_rut` | INT (FK) | Referencia al dueño del ticket. |

---

## 🔌 Integración Middleware

El sistema expone un consumidor de RabbitMQ en la cola `new_ticket`.

### Formato del Mensaje (JSON)
El Middleware debe enviar los tickets con esta estructura exacta:

```json
{
  "id": "EXT-UUID-1234",    
  "rut": 12345678,       
  "price": 5000.00,      
  "event": "Nombre del Evento" 
}
```

*   **rut:** Campo crítico. Si el RUT no existe en la DB, se crea un usuario placeholder.

---

## 🛠 Instalación y Ejecución

### Requisitos
*   Docker
*   Docker Compose

### Pasos
1.  **Configuración:**
    Copia el archivo de ejemplo y ajusta si es necesario (puertos, credenciales):
    ```bash
    cp .env.example .env
    ```

2.  **Levantar el Entorno:**
    Construye y levanta los contenedores (App2, MariaDB, RabbitMQ):
    ```bash
    docker compose up -d --build
    ```

3.  **Acceder:**
    *   **Web:** `http://localhost:5002`
    *   **RabbitMQ Admin:** `http://localhost:15672` (user: guest, pass: guest)

4.  **Simular Middleware (Prueba):**
    Ejecuta el script incluido para enviar tickets de prueba:
    ```bash
    pip install pika
    python3 simulate_middleware.py
    ```

---

## 📊 Diagramas

A continuación se presentan los diagramas de diseño del sistema.

### Diagrama de Casos de Uso
*(Espacio para insertar diagrama_de_casos_de_uso.txt / .png)*
<!-- Inserta aquí tu imagen: ![Casos de Uso](path/to/image.png) -->

### Diagrama de Clases
*(Espacio para insertar diagrama_de_clases.txt / .png)*
<!-- Inserta aquí tu imagen: ![Clases](path/to/image.png) -->

### Diagrama de Base de Datos (ER)
*(Espacio para insertar diagrama_de_base_de_datos.txt / .png)*
<!-- Inserta aquí tu imagen: ![ER](path/to/image.png) -->

### Diagramas de Secuencia
#### Recepción de Ticket (Middleware)
*(Espacio para diagrama_de_secuencia_RecepciónTicketMiddleware.txt)*

#### Pago de Ticket
*(Espacio para diagrama_de_secuencia_PagoTicket.txt)*

#### Devolución de Ticket
*(Espacio para diagrama_de_secuencia_DevolverTicket.txt)*
