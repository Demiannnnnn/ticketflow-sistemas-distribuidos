# 📋 TODO — TicketFlow: Refactor & Completar para Portafolio

> **Estado actual:** Proyecto universitario incompleto de 3 aplicaciones distribuidas conectadas por un middleware.
> Las 3 apps funcionan como silos parcialmente conectados. La integración end-to-end está rota.
>
> **Objetivo:** Convertir este proyecto en un sistema distribuido cohesivo, funcional y profesional
> digno de un portafolio de ingeniería de software.

---

## 📐 Arquitectura Actual del Sistema

```
                        ┌──────────────────────────────────────────────────┐
                        │              ticketflow_network                  │
                        │                                                  │
                        │  ┌─────────┐   ┌────────────┐   ┌───────────┐  │
                        │  │  etcd   │   │  RabbitMQ  │   │    App3   │  │
                        │  │ (DCS)   │   │  :5672     │   │  Flask    │  │
                        │  └─────────┘   │  :15672    │   │  :5003    │  │
                        │                └────────────┘   └─────┬─────┘  │
                        │                                       │        │
                        │  ┌──────────┐  ┌────────────────┐     │        │
                        │  │ HAProxy  │  │     Nginx      │◄────┘        │
                        │  │ DB LB    │  │  App1 LB :8083 │              │
                        │  │ :5432    │  └───────┬────────┘              │
                        │  │ :5433    │          │                       │
                        │  └────┬─────┘   ┌──────┴──────┐               │
                        │       │         │             │               │
                        │  ┌────┴─────┐  ┌┴──────┐ ┌───┴────┐          │
                        │  │ Patroni  │  │App1   │ │App1    │          │
                        │  │ Master + │  │Rep.1  │ │Rep.2   │          │
                        │  │ Slave    │  │Go:8080│ │Go:8080 │          │
                        │  │ PG 15    │  └───────┘ └────────┘          │
                        │  └──────────┘                                 │
                        │                                               │
                        │  ┌──────────────┐                             │
                        │  │  Middleware   │ ← Publica en RabbitMQ      │
                        │  │  Go+Gin:8000 │   pero NO conecta con App2 │
                        │  └──────────────┘                             │
                        └──────────────────────────────────────────────────┘

                        ┌──────────────────────────────────────────────────┐
                        │              app2_network (172.18.0.0/16)        │
                        │                                                  │
                        │  ┌──────────────┐  ┌──────────────┐             │
                        │  │  Nginx LB    │  │ Orchestrator │             │
                        │  │  HTTP :80    │  │  HA :3000    │             │
                        │  │  TCP  :6002  │  └──────┬───────┘             │
                        │  └──────┬───────┘         │                     │
                        │         │          ┌──────┴───────┐             │
                        │  ┌──────┴──────┐   │  ProxySQL    │             │
                        │  │  App2 x2    │   │  :6033/:6032 │             │
                        │  │  Flask      │   └──────┬───────┘             │
                        │  │  + TCP      │          │                     │
                        │  │  Listener   │   ┌──────┼───────┐            │
                        │  └─────────────┘   │      │       │            │
                        │                   db1    db2    db3             │
                        │                 Master  Slave  Slave            │
                        │                 MariaDB (GTID Replication)      │
                        └──────────────────────────────────────────────────┘
```

---

## 🚨 Rupturas Críticas de Integración (El Sistema NO Funciona End-to-End)

Estas son las fallas fundamentales que impiden que el sistema funcione como un todo:

### RUPTURA 1: Aislamiento de Red Docker
- `app2` y `app2_nginx` están **exclusivamente** en `app2_network`.
- `middleware` y `rabbitmq` están **exclusivamente** en `ticketflow_network`.
- **Resultado:** Es físicamente imposible que el Middleware se comunique con App2.

### RUPTURA 2: Incompatibilidad de Protocolos
- El **Middleware** (Go) publica mensajes en la cola RabbitMQ `orden_creada`.
- **App2** (Python) escucha en un **Socket TCP crudo** (puerto 6002), NO consume de RabbitMQ.
- Jamás se implementó la conexión entre ambos.

### RUPTURA 3: Incompatibilidad de Esquema de Datos
- **App3 → Middleware** envía: `{"event_id": "1", "user_id": "123", "quantity": 1}`
- **App2** espera recibir: `{"id": "UUID", "rut": 12345678, "price": 5000.0, "event": "Nombre"}`
- Los campos no coinciden en absoluto.

### RUPTURA 4: Identidad de Usuario Inexistente
- **App3** hardcodea `user_id: 123` en el JavaScript del frontend.
- **App2** requiere un RUT chileno real para asociar tickets y gestionar pagos.
- No existe flujo de autenticación compartido entre las apps.

### RUPTURA 5: Canal de Retorno Inexistente
- **App2** intenta notificar vía TCP a `MIDDLEWARE_NOTIFY_HOST:7002` (eventos `TICKET_PAID`, `TICKET_REFUNDED`).
- **No existe ningún listener** implementado en el Middleware en ese puerto.

---

## ✅ Tareas Organizadas por Componente

### Leyenda de Prioridad
- 🔴 **Crítico** — El sistema no funciona sin esto
- 🟠 **Alto** — Necesario para calidad de portafolio
- 🟡 **Medio** — Mejora significativa de calidad
- 🟢 **Bajo** — Nice-to-have / polish

---

## 1. 🔗 Integración del Sistema (Cross-Cutting)

### 1.1 Unificar Redes Docker
- [x] 🔴 Conectar `app2` y `app2_nginx` a `ticketflow_network` en `docker-compose.yml` ✅
- [x] 🔴 Conectar `middleware` a `app2_network` (o usar red compartida) ✅
- [ ] 🟡 Documentar el mapa de redes y puertos en el README

### 1.2 Resolver Integración Middleware ↔ App2
- [x] 🔴 **Opción A (Recomendada):** Implementar un consumidor RabbitMQ nativo en App2 usando `pika` (ya está en `requirements.txt`), que consuma de la cola `orden_creada` y ejecute `TicketService.receive_external_ticket()` ✅
- [ ] 🔴 **Opción B:** Actualizar el Middleware en Go para que consuma de RabbitMQ y reenvíe a App2 vía TCP socket
- [x] 🔴 Implementar listener TCP en el Middleware (puerto 7002) para recibir notificaciones de App2 (`TICKET_PAID`, `TICKET_REFUNDED`) ✅

### 1.3 Estandarizar Contrato de Datos (DTOs)
- [x] 🔴 Definir un esquema unificado de mensaje entre las 3 apps: ✅
  ```json
  {
    "order_id": "UUID",
    "event_id": "int",
    "event_name": "string",
    "seat_id": "int",
    "user_rut": "string (con DV)",
    "price": "decimal",
    "timestamp": "ISO-8601"
  }
  ```
- [x] 🔴 Actualizar App3, Middleware y App2 para usar este esquema ✅
- [x] 🟠 Agregar validación de esquema en cada punto de entrada ✅

### 1.4 Implementar Flujo de Identidad de Usuario
- [x] 🔴 Eliminar `user_id: 123` hardcodeado en App3 ✅
- [x] 🔴 Implementar formulario de ingreso de RUT en App3 (o sesión compartida) ✅
- [x] 🟠 Propagar el RUT a través de todo el flujo: App3 → App1 → Middleware → App2 ✅

### 1.5 Transacciones Distribuidas / Patrón Saga
- [x] 🟠 Implementar compensación: si el Middleware falla tras la reserva en App1, liberar el asiento automáticamente ✅
- [x] 🟠 Agregar endpoint `DELETE /api/reserve` o `POST /api/reserve/:id/cancel` en App1 ✅
- [x] 🟠 App3 debe retornar error real (no HTTP 200) cuando la facturación falla ✅

---

## 2. 🏗️ App1 — Gestor de Recintos y Reservas (Go + PostgreSQL/Patroni)

### 2.1 Refactorización de Arquitectura del Backend
- [ ] 🟠 Reestructurar el proyecto Go en layout estándar:
  ```
  app1/
  ├── cmd/server/main.go
  ├── internal/
  │   ├── config/       # Variables de entorno
  │   ├── domain/       # Event, Seat, Reservation structs
  │   ├── repository/   # PostgreSQL queries (pgx)
  │   ├── service/      # Lógica de negocio
  │   ├── handler/      # Handlers Gin + DTOs
  │   └── worker/       # Background jobs
  ```
- [ ] 🟡 Migrar de `lib/pq` (en modo mantenimiento) a `jackc/pgx/v5`
- [x] 🟡 Reemplazar `[]map[string]interface{}` por structs tipados en respuestas JSON ✅

### 2.2 Bugs y Problemas Críticos del Backend
- [x] 🔴 **Eliminar `sync.RWMutex`**: El mutex en memoria NO sincroniza entre réplicas distribuidas. Solo `SELECT ... FOR UPDATE` de PostgreSQL provee protección real. El mutex además bloquea lecturas innecesariamente ✅
- [x] 🔴 **Race condition en `initDB()`**: Cuando ambas réplicas arrancan simultáneamente, ambas ejecutan `insertSampleData()` causando duplicados. Solución: usar `pg_advisory_lock` y `ON CONFLICT DO NOTHING` ✅
- [x] 🟠 Configurar pool de conexiones DB: `SetMaxOpenConns()`, `SetMaxIdleConns()`, `SetConnMaxLifetime()` ✅
- [x] 🟠 Implementar `Graceful Shutdown` con `http.Server` + `signal.NotifyContext` ✅
- [x] 🟡 Validar parámetros de ruta (`:id` debe ser int válido) ✅

### 2.3 Completar Ciclo de Vida de Reservas
- [x] 🔴 Agregar columna `reservation_expires_at` a la tabla `seats` ✅
- [x] 🔴 Implementar worker background que libere reservas expiradas: ✅
  ```sql
  UPDATE seats SET status='available', user_id=NULL
  WHERE status='reserved' AND reservation_expires_at < NOW();
  ```
- [x] 🔴 Agregar endpoint `POST /api/reserve/:id/confirm` (reserved → sold) ✅
- [x] 🔴 Agregar endpoint `POST /api/reserve/:id/cancel` (reserved → available) ✅
- [x] 🟠 Agregar endpoint individual `GET /api/events/:id` (App3 lo necesita) ✅

### 2.4 Read/Write Splitting en PostgreSQL
- [ ] 🟡 Configurar dos pools de conexión en Go:
  - `MasterPool` → `haproxy:5432` (para escrituras / reservas)
  - `ReplicaPool` → `haproxy:5433` (para lecturas / GET events, seats)
- [ ] 🟡 Actualizar `patroni.yml`: reemplazar `wal_keep_segments: 8` (deprecado en PG 13+) por `wal_keep_size: 128MB`

### 2.5 Frontend de App1
- [ ] 🟡 Agregar polling o WebSockets/SSE para el modal de asientos (actualmente no se actualiza en tiempo real cuando otro usuario reserva)
- [ ] 🟡 Convertir asientos de `<div onclick>` a `<button>` semánticos con `tabindex`, `aria-label`, `aria-pressed`
- [ ] 🟡 Agregar `role="dialog"`, `aria-modal="true"` y focus trapping al modal
- [ ] 🟡 Corregir contraste de color: texto blanco sobre naranja (#FF9800) falla WCAG AA (ratio 2.1:1, mínimo 4.5:1)
- [ ] 🟢 Agregar indicador visual de expiración de reserva (countdown timer)
- [ ] 🟢 Permitir selección múltiple de asientos

### 2.6 Infraestructura App1
- [x] 🟡 ~~Eliminar bloque `listen mariadb` muerto en `haproxy.cfg` (residuo de pruebas)~~ ✅
- [ ] 🟡 Agregar `USER 10001:10001` (non-root) en el Dockerfile de runtime
- [ ] 🟡 Descomentar/crear directorio `static/` o eliminar `router.Static("/static", "./static")` muerto en `main.go`
- [ ] 🟡 Fix `entrypoint.sh`: usar `hostname -I | awk '{print $1}'` en vez de `hostname -i` (falla con múltiples IPs)
- [ ] 🟢 Agregar compresión gzip, rate limiting y security headers en `nginx.conf`

---

## 3. 🎫 App2 — Motor de Facturación y Tickets (Flask + MariaDB)

### 3.1 Bugs Críticos del Frontend
- [x] 🔴 **`base.html` línea 22**: Cambiar `session.get('user_id')` por `session.get('user_rut')`. **La navbar NUNCA muestra el estado de login actual** — siempre muestra "Login" y "Register", nunca "My Tickets" ni "Logout" ✅
- [x] 🔴 **`base.html`**: Agregar CSS de Bootstrap Icons (`bootstrap-icons@1.11.3`). Todos los iconos `<i class="bi ...">` están rotos y no se renderizan ✅
- [x] 🟠 **`payment.html`**: Agregar atributos `name` a los inputs del formulario de pago (`cardName`, `cardNumber`, `expiry`, `cvv`) ✅
- [ ] 🟡 Unificar idioma: actualmente mezcla inglés ("Secure Payment Gateway") con español ("Pagar Ahora")

### 3.2 Seguridad del Backend
- [x] 🔴 **Implementar protección CSRF**: Ningún formulario POST tiene tokens CSRF. Usar `Flask-WTF` ✅
- [x] 🔴 **`SECRET_KEY`**: Validar que `APP2_SECRET_KEY` no sea `None` al iniciar (fail fast) ✅
- [ ] 🟠 Integrar `Flask-Login` con decorador `@login_required` centralizado (actualmente cada ruta chequea `g.user_rut is None` manualmente)
- [ ] 🟠 Agregar validación de complejidad de contraseña
- [ ] 🟡 Agregar rate limiting en endpoints de autenticación
- [ ] 🟡 Agregar confirmación modal antes de acciones irreversibles (reembolsos)

### 3.3 Modelo de Datos y Base de Datos
- [ ] 🟠 **Cambiar `Float` por `Numeric(10, 2)`** en `price` (Ticket) y `amount` (Payment). `Float` causa errores de redondeo monetario por IEEE 754
- [ ] 🟠 **RUT como `VARCHAR(12)`**: Actualmente es `INT`, lo que impide almacenar el dígito verificador 'K'. Implementar algoritmo Módulo 11 de validación
- [ ] 🟠 Reemplazar `db.create_all()` en runtime por **Flask-Migrate (Alembic)** para control de versiones de esquema
- [x] 🟠 Configurar pool de SQLAlchemy: `pool_size=10`, `pool_recycle=3600`, `pool_pre_ping=True` (necesario para ProxySQL) ✅
- [ ] 🟡 Agregar `unique=True` a `Payment.ticket_id` en el modelo SQLAlchemy (existe en SQL pero no en ORM)

### 3.4 Bugs del Backend
- [x] 🟠 **`notification_client.py` línea 16**: `str(os.times())` genera timestamps de CPU del proceso, NO timestamps reales. Cambiar a `datetime.now(timezone.utc).isoformat()` ✅
- [x] 🟠 **`services.py` `AuthService.register`**: Al activar un placeholder, cambia el email sin verificar si ya existe en otro usuario → causa `IntegrityError` 500 no controlado ✅
- [x] 🟡 Agregar `db.session.rollback()` explícito en bloques `try/except` de `services.py` ✅
- [ ] 🟡 Reemplazar `print()` por módulo `logging` con niveles y formato estructurado

### 3.5 Producción y DevOps App2
- [ ] 🟠 Reemplazar `flask run` por **Gunicorn**: `gunicorn -w 4 -b 0.0.0.0:5002 run:app`
- [ ] 🟠 Separar web server (Gunicorn) del consumer de mensajes en contenedores distintos
- [ ] 🟡 Resolver race condition de `replicas: 2`: ambas réplicas levantan `TCPServerAdapter` en puerto 6002 independientemente, sin coordinación de mensajes
- [x] 🟡 ~~Eliminar archivos `__pycache__/` del repositorio y agregar al `.gitignore`~~ ✅

### 3.6 UX del Frontend App2
- [ ] 🟡 Agregar `autocomplete` a campos de formularios (`autocomplete="email"`, `autocomplete="current-password"`)
- [ ] 🟡 Agregar campo de confirmación de contraseña en registro
- [ ] 🟡 Agregar validación client-side del formato de RUT
- [x] 🟡 Corregir link de navbar brand (actualmente `href="#"`) ✅
- [ ] 🟢 Rediseñar templates con un estilo visual más moderno y consistente

### 3.7 Problema Arquitectónico: Read-Your-Own-Writes
- [ ] 🟡 ProxySQL enruta todos los `SELECT` a réplicas (Hostgroup 20). Tras un `INSERT` + `redirect()`, el usuario puede ver datos desactualizados por replication lag. Considerar usar hints de query (`/* hostgroup=10 */`) para lecturas post-escritura

---

## 4. 🛒 App3 — Portal de Venta de Entradas (Flask)

### 4.1 Backend
- [x] 🔴 **Eliminar `user_id: 123` hardcodeado** en `seats.html` línea 146. Implementar input de RUT o sesión ✅
- [x] 🔴 **Compensación de transacciones**: Si el Middleware falla, NO retornar HTTP 200. Implementar rollback del asiento en App1 ✅
- [x] 🟠 Externalizar URLs hardcodeadas a variables de entorno (`APP1_API_URL`, `APP1_RESERVE_URL`, `MIDDLEWARE_URL`) ✅
- [x] 🟠 Validar `request.get_json()` contra `None` (evitar `AttributeError: 'NoneType'`) ✅
- [x] 🟡 Eliminar `pika` de `requirements.txt` (no se usa; App3 se comunica vía HTTP) ✅
- [x] 🟡 Optimizar `ver_asientos`: actualmente hace GET a `/api/events` y itera todos para encontrar uno, luego hace otro GET. Usar endpoint individual `GET /api/events/:id` ✅

### 4.2 Frontend
- [x] 🟡 Agregar modal de confirmación antes de reservar (mostrar precio, evento, asiento) ✅
- [x] 🟡 Eliminar `<div id="global-message">` no utilizado y comentarios residuales en JS ✅
- [ ] 🟢 Permitir selección de múltiples asientos antes de confirmar
- [ ] 🟢 Mostrar precio y categoría/zona del asiento

### 4.3 Producción
- [ ] 🟠 Reemplazar servidor de desarrollo Flask por **Gunicorn**
- [ ] 🟡 Agregar health check en `docker-compose.yml` para App3
- [x] 🟡 Corregir dependencia en compose: App3 depende de `rabbitmq` pero debería depender de `nginx` y `middleware` ✅

---

## 5. 🔀 Middleware — Bus de Mensajes (Go + Gin + RabbitMQ)

### 5.1 Bugs y Problemas Críticos
- [x] 🔴 **Connection Thrashing**: Cada petición HTTP abre y cierra una conexión AMQP completa (TCP handshake + auth + channel). Implementar **singleton de conexión persistente** con pool de canales reutilizables ✅
- [x] 🔴 **Implementar listener TCP en puerto 7002** para recibir notificaciones de retorno de App2 (`TICKET_PAID`, `TICKET_REFUNDED`) ✅
- [x] 🟠 Implementar `Graceful Shutdown` con `os.Signal` + `context.Context` ✅
- [x] 🟡 Corregir `go.sum` vacío en el repositorio (0 bytes) ✅

### 5.2 Mejoras para Portafolio
- [x] 🟠 Agregar endpoint `GET /health` con verificación de conexión a RabbitMQ ✅
- [ ] 🟡 Agregar métricas Prometheus (`/metrics`)
- [ ] 🟡 Usar logging estructurado (`zerolog` o `zap`)
- [x] 🟡 Agregar retry con backoff exponencial para conexión a RabbitMQ al arranque ✅

---

## 6. 🐳 Docker Compose y Orquestación

### 6.1 Correcciones
- [x] 🔴 Conectar servicios a las redes correctas (ver sección 1.1) ✅
- [ ] 🟠 Agregar health checks para `middleware` y `app3`
- [x] 🟠 Corregir dependencias de `app3`: cambiar `depends_on: rabbitmq` por `depends_on: [nginx, middleware]` ✅
- [ ] 🟡 Eliminar volumen de desarrollo `./app2:/usr/src/app` (sobreescribe contenido del contenedor)

### 6.2 Mejoras
- [ ] 🟡 Agregar perfiles de Docker Compose (`--profile dev` vs `--profile prod`)
- [ ] 🟢 Agregar contenedor de monitoreo (Prometheus + Grafana) para visualizar métricas del cluster
- [ ] 🟢 Agregar etcd multi-nodo (actualmente es SPOF para Patroni)

---

## 7. 📄 Documentación y Higiene del Repositorio

### 7.1 README.md
- [ ] 🟠 Corregir inexactitudes:
  - Dice que App2 consume de cola `new_ticket` en RabbitMQ (falso, usa TCP Socket)
  - Referencia a `simulate_middleware.py` (archivo real: `simulate_tcp_middleware.py`)
  - Indica MariaDB en puerto `3306` (ProxySQL expone `6033`)
- [ ] 🟠 Agregar diagrama de arquitectura actualizado
- [ ] 🟡 Agregar instrucciones claras de setup paso a paso
- [ ] 🟡 Agregar sección de tecnologías utilizadas con badges

### 7.2 `.env.example`
- [x] 🟠 Agregar variables faltantes: ✅
  - App1: credenciales PostgreSQL, puertos
  - App3: `APP3_PORT`, `APP1_API_URL`, `MIDDLEWARE_URL`
  - Middleware: `RABBITMQ_URL`, `LISTEN_PORT`
- [x] 🟡 Agregar comentarios explicativos a cada variable ✅

### 7.3 `.gitignore`
- [x] 🟡 ~~Agregar patrones faltantes~~ ✅ (Python, Go, IDE, OS, Docker patterns agregados)
- [x] 🟡 ~~Eliminar `.DS_Store` commiteado: `git rm --cached .DS_Store`~~ ✅
- [x] 🟡 ~~Eliminar archivos `__pycache__/*.pyc` commiteados~~ ✅

### 7.4 Diagramas
- [ ] 🟡 Crear diagrama de arquitectura C4 global del sistema (contexto + contenedores)
- [ ] 🟡 Crear diagramas de secuencia para App1 y App3 (actualmente solo existen para App2)
- [ ] 🟡 Crear diagrama de secuencia del flujo completo end-to-end
- [ ] 🟢 Corregir caso de uso duplicado `(Registrarse)` en `diagrama_de_casos_de_uso.uml`
- [ ] 🟢 Corregir typo `Loggin` → `Login` en nombre de diagrama de secuencia

---

## 8. 🧪 Testing (Inexistente — Crear desde Cero)

- [ ] 🟠 **App1 (Go)**: Unit tests con `testify` para handlers y services
- [ ] 🟠 **App2 (Python)**: Unit tests con `pytest` y fixtures SQLite in-memory
- [ ] 🟠 **App3 (Python)**: Tests de integración de rutas con `pytest` + `requests-mock`
- [ ] 🟡 **Middleware (Go)**: Tests con mock de RabbitMQ
- [ ] 🟡 **Integration tests**: Docker Compose test profile con health checks end-to-end
- [ ] 🟢 **App1 (Go)**: Integration tests con `testcontainers-go` para PostgreSQL

---

## 9. 🎨 Mejoras Visuales Globales para Portafolio

- [ ] 🟠 Unificar diseño visual entre las 3 apps (misma paleta de colores, tipografía, estilo de cards)
- [ ] 🟠 Crear una landing page o dashboard central que conecte las 3 apps
- [ ] 🟡 Hacer todas las interfaces fully responsive (mobile-first)
- [ ] 🟡 Agregar loading spinners y feedback visual en operaciones asíncronas
- [ ] 🟡 Implementar notificaciones toast para éxito/error en vez de recargar la página
- [ ] 🟢 Considerar migrar frontends a un framework moderno (React/Vue/Svelte) como SPA con API REST

---

## 📊 Resumen de Tareas por Prioridad

| Prioridad | Cantidad | Descripción |
| :--- | :---: | :--- |
| 🔴 Crítico | ~20 | Sistema roto, bugs bloqueantes, integración inexistente |
| 🟠 Alto | ~30 | Calidad de producción, seguridad, arquitectura profesional |
| 🟡 Medio | ~35 | Mejoras de calidad, UX, documentación, accesibilidad |
| 🟢 Bajo | ~12 | Polish, nice-to-have, optimizaciones avanzadas |

---

## 🗺️ Orden de Ejecución Sugerido

### Fase 1: Hacer que funcione end-to-end (🔴 Críticos)
1. Unificar redes Docker
2. Implementar consumidor RabbitMQ en App2 (o adaptar Middleware)
3. Estandarizar contrato de datos entre apps
4. Fixear bug de navbar en App2 (`user_id` → `user_rut`)
5. Eliminar `user_id: 123` hardcodeado en App3
6. Fixear connection thrashing del Middleware

### Fase 2: Robustez y seguridad (🟠 Altos)
1. Protección CSRF en App2
2. Transacciones compensatorias (Saga pattern)
3. Ciclo de vida completo de reservas (expiración, confirmación, cancelación)
4. Servidores de producción (Gunicorn)
5. Refactorización Go (layout estándar, pgx)
6. Tests unitarios

### Fase 3: Calidad de portafolio (🟡 Medios + 🟢 Bajos)
1. Unificar diseño visual
2. Documentación completa
3. Diagramas C4
4. Accesibilidad (ARIA, contraste, semántica)
5. Monitoreo (Prometheus + Grafana)
6. Landing page / dashboard

---

> **Nota:** Este análisis fue generado a partir de una revisión exhaustiva línea por línea de
> todos los archivos del repositorio (Go, Python, HTML, SQL, YAML, Shell, UML, DBML).
> Última actualización: 2026-08-30
