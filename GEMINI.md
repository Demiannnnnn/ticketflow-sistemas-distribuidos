# TicketFlow Project Context - GEMINI.md

## 🚀 Project Overview
**TicketFlow** is a distributed system for ticket sales designed for high availability and fault tolerance. It decouples reservation, billing, and notification logic into separate services.

## 🏗️ System Architecture

The system consists of 4 main components managed via Docker Compose:

### 1. App1 - Reservation Manager (Go)
*   **Role:** Manages event inventory and seat reservations. Source of truth for availability.
*   **Tech Stack:** Go (Gin framework).
*   **Database:** Highly Available PostgreSQL Cluster.
    *   **Management:** **Patroni** (using **Etcd** for DCS).
    *   **Routing:** **HAProxy** (Port 5432/5433) routes to Master/Replica.
    *   **Load Balancing:** Nginx sits in front of 2 application replicas (`app1_replica1`, `app1_replica2`).
*   **Communication:**
    *   **Input:** HTTP API (Port 8083).
    *   **Output:** Sends reservation data via **TCP** to `app2`.
*   **Key Configuration:**
    *   `app1/db/patroni.yml`: Patroni config. **Crucial:** Uses `post_init` hook `/usr/local/bin/create_db.sh` to auto-create `ticketflow` DB.
    *   `app1/db/entrypoint.sh`: Sets up runtime env vars (IP injection) and permissions.

### 2. App2 - Billing & Ticket Engine (Python)
*   **Role:** Handles user management, ticket creation, payments, and check-in.
*   **Tech Stack:** Python (Flask).
*   **Architecture:** **Dual Process Container**.
    *   **Web Server:** Flask app for user UI/API.
    *   **Socket Listener:** Background process (`run_listener.py`) listening for TCP connections from `app1`.
*   **Database:** Highly Available MariaDB Cluster.
    *   **Components:** 3 MariaDB nodes, **ProxySQL** (R/W splitting), and **Orchestrator** (Failover management).
*   **Communication:**
    *   **Input:** HTTP (Web UI) & TCP (from `app1`).
    *   **Output:** Sends payment events via **TCP** to `middleware`.

### 3. Middleware (Go)
*   **Role:** Event Bridge / Orchestrator.
*   **Function:** Listens for TCP events from `app2` (e.g., "Ticket Paid") and publishes them to **RabbitMQ**.
*   **Tech Stack:** Go.
*   **Communication:** TCP Server -> RabbitMQ Publisher.

### 4. App3 - Sales Portal (Python)
*   **Role:** Asynchronous User Portal.
*   **Function:** Consumes messages from RabbitMQ to finalize sales/notifications.
*   **Tech Stack:** Python.

## 🌐 Network Infrastructure
*   **`ticketflow_network`:** Main network connecting App1, App3, Middleware, RabbitMQ, Etcd, and App1's DB layer.
*   **`app2_network`:** Dedicated network for App2's MariaDB cluster isolation.

## 🛠️ Key Configurations & Fixes (Important for Maintenance)

### PostgreSQL / Patroni (App1)
*   **Etcd V2 API:** Patroni requires Etcd v2 API.
    *   **Fix:** `ETCD_ENABLE_V2=true` must be set in the `etcd` service in `docker-compose.yml`.
*   **IP Binding:** Patroni nodes must advertise their Docker container IP, not localhost.
    *   **Mechanism:** `entrypoint.sh` dynamically grabs `hostname -i` and substitutes it in `patroni.yml` at runtime.
*   **Access Control:** `patroni.yml` includes specific `pg_hba` entries to allow connections from the Docker subnet (`0.0.0.0/0 md5` for simplicity in dev).
*   **Auto-Init:** A `create_db.sh` script is injected into the image and defined as a `post_init` hook in `patroni.yml` to ensure the `ticketflow` database is created automatically upon cluster bootstrap.

### HAProxy
*   **Configuration:** `app1/haproxy.cfg` handles routing for Postgres Master (`postgres_master`) and Replicas (`postgres_replica`).
*   **Note:** MariaDB routing sections in HAProxy should be disabled if MariaDB nodes are on a different network (`app2_network`) to avoid startup errors.

## 📂 Important File Locations
*   `docker-compose.yml`: Main orchestration file.
*   `app1/db/patroni.yml`: Patroni configuration template.
*   `app1/db/entrypoint.sh`: Startup logic for Patroni containers.
*   `app1/db/create_db.sh`: Script to create the initial database.
*   `app2/run_listener.py`: TCP Listener entry point for App2.

## 🚑 Troubleshooting
*   **App1 DB Connection Failures:** Check `app1_haproxy` logs. If `Connection refused`, verify Patroni cluster status and `pg_hba` rules.
*   **"Database does not exist":** If `ticketflow` DB is missing, check `app1_patroni_master` logs for `post_init` hook execution or run `docker exec app1_patroni_master psql -U postgres -c "CREATE DATABASE ticketflow;"`.
*   **Etcd Errors:** Ensure `ETCD_ENABLE_V2=true` is set.

---
*Generated for Gemini Context Awareness - 2025*
