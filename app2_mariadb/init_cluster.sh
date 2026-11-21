#!/bin/bash
set -e

mysql_cmd() {
    if type docker_process_sql >/dev/null 2>&1; then
        docker_process_sql "$@"
    else
        mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" "$@"
    fi
}

mysql_cmd <<EOSQL
-- Usuarios de Sistema para Arquitectura HA

-- 1. Usuario para Replicación (Slave -> Master)
CREATE USER IF NOT EXISTS '${APP2_REPL_USER:-repl_user}'@'%' IDENTIFIED BY '${APP2_REPL_PASSWORD}';
GRANT REPLICATION SLAVE ON *.* TO '${APP2_REPL_USER:-repl_user}'@'%';

-- 2. Usuario para Orchestrator (Topology Manager)
CREATE USER IF NOT EXISTS '${APP2_ORCH_USER:-orch_user}'@'%' IDENTIFIED BY '${APP2_ORCH_PASSWORD}';
GRANT SUPER, PROCESS, REPLICATION SLAVE, REPLICATION CLIENT, RELOAD ON *.* TO '${APP2_ORCH_USER:-orch_user}'@'%';

-- 3. Usuario para ProxySQL Monitor
CREATE USER IF NOT EXISTS '${APP2_MONITOR_USER:-monitor_user}'@'%' IDENTIFIED BY '${APP2_MONITOR_PASSWORD}';
GRANT USAGE ON *.* TO '${APP2_MONITOR_USER:-monitor_user}'@'%';

FLUSH PRIVILEGES;
EOSQL
