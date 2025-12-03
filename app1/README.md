# App1 - TicketFlow: Gestor de Recintos y Reservas

Sistema de gestión de eventos y reserva de asientos desarrollado en Go con PostgreSQL, implementando alta disponibilidad mediante réplicas y Patroni.

## 🏗️ Arquitectura

### Componentes

1. **Load Balancer (Nginx)**
   - Distribuye el tráfico entre las réplicas de App1
   - Puerto: `8080`
   - Algoritmo: Least Connections

2. **App1 - Réplicas (Go + Gin)**
   - `app1_replica1` y `app1_replica2`
   - Backend API RESTful
   - Frontend integrado (HTML/JS)
   - Prevención de race conditions con mutex

3. **Base de Datos PostgreSQL (Patroni)**
   - **Master**: Escritura y lectura
   - **Slave**: Réplica de solo lectura
   - **Orquestador**: Patroni con etcd
   - **HAProxy**: Balanceo automático hacia master/slave

## 🚀 Inicio Rápido

### Prerequisitos

- Docker
- Docker Compose

### Iniciar el Sistema

```bash
cd app1
docker-compose up -d
```

### Verificar Estado

```bash
# Ver logs de los contenedores
docker-compose logs -f

# Ver estado de salud
docker-compose ps

# Health check de Nginx
curl http://localhost:8080/health

# Ver estadísticas de HAProxy (PostgreSQL)
open http://localhost:7000
```

## 📋 Endpoints API

### Health Check
```bash
GET /health
```

### Obtener Eventos
```bash
GET /api/events
```

### Obtener Asientos de un Evento
```bash
GET /api/events/:id/seats
```

### Reservar Asiento
```bash
POST /api/reserve
Content-Type: application/json

{
  "seat_id": 1,
  "user_id": 123
}
```

### Información de Instancia
```bash
GET /api/instance
```

## 🗄️ Base de Datos

### Estructura

**Tabla: events**
- `id` (SERIAL PRIMARY KEY)
- `name` (VARCHAR)
- `venue` (VARCHAR)
- `date` (VARCHAR)
- `total_seats` (INT)
- `description` (TEXT)

**Tabla: seats**
- `id` (SERIAL PRIMARY KEY)
- `event_id` (FK → events.id)
- `seat_number` (VARCHAR)
- `status` (VARCHAR: available, reserved, sold)
- `reserved_at` (TIMESTAMP)
- `user_id` (INT)

### Patroni - Alta Disponibilidad

Patroni gestiona automáticamente:
- Replicación master-slave
- Failover automático
- Health checks
- Sincronización de datos

**Conectarse directamente a PostgreSQL:**

```bash
# A través de HAProxy (recomendado)
psql -h localhost -p 5432 -U postgres -d ticketflow

# Directamente al master
docker exec -it app1_patroni_master psql -U postgres -d ticketflow

# Directamente al slave
docker exec -it app1_patroni_slave psql -U postgres -d ticketflow
```

## 🔧 Configuración

### Variables de Entorno

**App1:**
- `INSTANCE_NAME`: Nombre de la instancia
- `PORT`: Puerto de la aplicación (default: 8080)
- `DB_HOST`: Host de PostgreSQL (default: haproxy)
- `DB_USER`: Usuario de PostgreSQL
- `DB_PASSWORD`: Contraseña de PostgreSQL
- `DB_NAME`: Nombre de la base de datos

## 🧪 Pruebas de Tolerancia a Fallos

### 1. Caída de Réplica de Aplicación

```bash
# Detener una réplica
docker stop app1_replica1

# El tráfico se redirige automáticamente a app1_replica2
curl http://localhost:8080/api/instance

# Reiniciar réplica
docker start app1_replica1
```

### 2. Caída de PostgreSQL Master

```bash
# Detener master
docker stop app1_patroni_master

# Patroni promueve automáticamente al slave como nuevo master
# Verificar en logs
docker-compose logs -f patroni_slave

# Ver estadísticas de HAProxy
open http://localhost:7000
```

### 3. Prueba de Concurrencia (Evitar Double-Booking)

```bash
# Ejecutar múltiples reservas simultáneas del mismo asiento
for i in {1..10}; do
  curl -X POST http://localhost:8080/api/reserve \
    -H "Content-Type: application/json" \
    -d '{"seat_id": 1, "user_id": '$i'}' &
done

# Solo UNA reserva debe ser exitosa
```

## 📊 Monitoreo

### Nginx Load Balancer
```bash
# Ver configuración activa
docker exec app1_nginx_lb cat /etc/nginx/nginx.conf

# Logs
docker-compose logs -f nginx
```

### HAProxy Stats
- URL: http://localhost:7000
- Muestra estado de master/slave PostgreSQL

### Logs de Aplicación
```bash
# Todas las réplicas
docker-compose logs -f app1_replica1 app1_replica2

# Una réplica específica
docker-compose logs -f app1_replica1
```

## 🛠️ Troubleshooting

### La aplicación no se conecta a la base de datos

```bash
# Verificar estado de Patroni
docker-compose logs patroni_master patroni_slave

# Verificar HAProxy
docker-compose logs haproxy

# Conectarse manualmente
psql -h localhost -p 5432 -U postgres -d ticketflow
```

### Nginx no balancea correctamente

```bash
# Verificar upstreams
docker exec app1_nginx_lb nginx -t

# Recargar configuración
docker-compose restart nginx
```

## 📝 Características Técnicas

### Prevención de Race Conditions
- Uso de `sync.RWMutex` en Go
- Transacciones SQL con `FOR UPDATE`
- Lock pesimista para evitar double-booking

### Alta Disponibilidad
- 2 réplicas de aplicación
- Load balancing con Nginx
- Replicación master-slave con Patroni
- Failover automático de base de datos

### Consistencia de Datos
- Consistencia eventual
- Transacciones ACID en PostgreSQL
- Replicación síncrona/asíncrona configurable

## 🔐 Seguridad

- Conexiones a base de datos con usuario/password
- Validación de entrada en API
- CORS configurado
- Health checks para evitar ruteo a servicios caídos

## 📦 Estructura del Proyecto

```
app1/
├── backend/
│   ├── main.go          # Aplicación Go principal
│   ├── go.mod           # Dependencias Go
│   └── go.sum           # Checksums de dependencias
├── frontend/
│   └── index.html       # Interfaz web
├── static/              # Archivos estáticos
├── Dockerfile           # Imagen Docker de App1
├── docker-compose.yml   # Orquestación de servicios
├── nginx.conf           # Configuración de Nginx LB
├── haproxy.cfg          # Configuración de HAProxy
└── README.md            # Esta documentación
```

## 🎯 SLA/SLO

- **Disponibilidad**: 99.9%
- **Latencia de reserva**: < 300ms (p99)
- **RTO (Recovery Time Objective)**: < 1 minuto
- **Tasa de errores**: < 0.01%

## 👥 Integrantes

- Catalina Herrera
- Camilo Fuentes
- Demian Maturana

## 📄 Licencia

Proyecto académico - Universidad de Talca
