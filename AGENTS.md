# AGENTS.md — TicketFlow Sistemas Distribuidos

## 1. Propósito del Proyecto
TicketFlow es una plataforma distribuida y tolerante a fallos para reserva, facturación y compra de entradas para eventos masivos. Diseñada con consistencia eventual, alta disponibilidad (HA) en bases de datos y desacoplamiento mediante colas de mensajería y sockets TCP.

## 2. Stack Tecnológico
- **App1 (Reservas):** Go 1.21, Gin, PostgreSQL 15 en clúster HA con Patroni, etcd v3.5 y HAProxy.
- **App2 (Facturación):** Python 3.8/Flask, SQLAlchemy, MariaDB 10.5 con replicación GTID (Master + 2 Slaves), ProxySQL 2.5 (read/write split) y OpenArk Orchestrator 3.2 (failover automático).
- **App3 (Portal de Venta):** Python 3.9/Flask con frontend Jinja2 y Bootstrap.
- **Middleware (Orquestador):** Go 1.21 con RabbitMQ 3 (AMQP 0-9-1) para procesamiento asíncrono de órdenes.
- **Infraestructura:** Docker Compose v3.8, Nginx LB.

## 3. Estructura de Carpetas
```
ticketflow-sistemas-distribuidos/
├── app1/                # Reservas (Go, Gin, Patroni, HAProxy)
├── app2/                # Facturación (Flask, SQLAlchemy, listener TCP)
├── app2_mariadb/        # MariaDB HA (my.cnf, init_cluster.sh, init.sql)
├── app2_nginx_lb/       # Balanceador Nginx para instancias de App2
├── app2_orchestrator/   # Orquestador de topología y failover
├── app2_proxysql/       # ProxySQL (balanceo de consultas y routing)
├── app2_scripts/        # Scripts auxiliares de replicación MariaDB
├── app3/                # Portal de venta interactivo (Flask)
├── middleware/          # Orquestador Go entre App3 y colas RabbitMQ
├── diagramas/           # Especificación visual (UML, DBML)
├── docker-compose.yml   # Orquestación global de todos los servicios
├── .env.example         # Plantilla documentada de variables de entorno
└── simulate_tcp_middleware.py # Simulador de eventos TCP para pruebas
```

## 4. Comandos de Verificación, Ejecución y Test
```bash
# Preparar entorno
cp .env.example .env

# Validar sintaxis de Compose
docker compose config

# Levantar infraestructura completa
docker compose up -d --build

# Verificación de sintaxis Python (en host)
python3 -m py_compile app2/run.py app2/run_listener.py app2/verify_api.py app2/verify_changes.py app2/app/*.py app3/app.py simulate_tcp_middleware.py

# Verificación de tests unitarios de App2 (requiere entorno Flask/SQLAlchemy)
DATABASE_URL="sqlite:///:memory:" python3 app2/verify_changes.py

# Simulación de eventos TCP
python3 simulate_tcp_middleware.py
```

## 5. Convenciones de Código
- **Go:** Código idiomático formateado con `gofmt`/`goimports`, manejo explícito de errores (`if err != nil`), variables de entorno leídas con `os.Getenv` y nombres en MAYÚSCULAS.
- **Python:** PEP 8, nombres en `snake_case`, constantes en `UPPER_SNAKE_CASE`, clases en `PascalCase`. Sin imports ni variables sin uso.
- **SQL / Docker:** Scripts bash con `set -e`, DDL idempotente (`IF NOT EXISTS`), healthchecks explícitos en Compose.

## 6. Reglas de Seguridad
- **Secretos:** NUNCA hardcodear credenciales, contraseñas, tokens ni hashes en código, scripts o Dockerfile.
- **Variables de Entorno:** Toda credencial debe inyectarse vía variables de entorno (`APP2_DB_PASSWORD`, `APP1_DB_PASSWORD`, etc.).
- **Versionado:** El archivo `.env` está estrictamente ignorado por `.gitignore` y JAMÁS se versiona ni se incluye en commits.
- **Plantillas:** Las nuevas credenciales deben registrarse en `.env.example` con valor `CHANGE_ME` y descripción explicativa.

## 7. Flujo Git
- **Ramas:** Todo trabajo de agentes se desarrolla en ramas de tipo `dev/*` (e.g., `dev/cleanup-2026-11`).
- **Integración:** Las ramas se integran hacia `develop-AGENTS` mediante Pull Request o revisión de orquestador.
- **Prohibido:** NUNCA hacer commit ni push directo a las ramas `main` ni `develop`.
- **Commits:** Mensajes en formato Conventional Commits en inglés (`feat:`, `fix:`, `chore:`, `refactor:`, `docs:`).
