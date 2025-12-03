#!/bin/bash

# Argumentos recibidos de Orchestrator
FAILURE_TYPE=$1
FAILURE_DESCRIPTION=$2
FAILED_HOST=$3
SUCCESSOR_HOST=$4

echo "[$(date)] Failover Event: $FAILURE_TYPE. New Master: $SUCCESSOR_HOST" >> /var/log/orchestrator-recovery.log

if [ -z "$SUCCESSOR_HOST" ]; then
    echo "Error: No successor host provided." >> /var/log/orchestrator-recovery.log
    exit 1
fi

# Conectar a ProxySQL y actualizar las tablas
# Puerto Admin ProxySQL: 6032
# Credenciales Admin por defecto: admin/admin
# Hostgroup 10: WRITER (Master)
# Hostgroup 20: READER (Slaves)

# 1. Mover el NUEVO master al Hostgroup 10 (Writer) y quitarlo del 20 (Reader si se desea lectura exclusiva)
# 2. Mover el VIEJO master (si revive) al Hostgroup 20 (Reader) - Orchestrator lo hará slave, ProxySQL debe saber que es reader.
# 3. Asegurar que todos los demás estén en HG 20.

# Nota: Por simplicidad, hacemos un "Reset" basándonos en el nuevo master.

PROXY_ADMIN_USER="admin"
PROXY_ADMIN_PASS="admin"
PROXY_HOST="proxysql"

mysql -u$PROXY_ADMIN_USER -p$PROXY_ADMIN_PASS -h $PROXY_HOST -P 6032 <<EOF
-- Mover el nuevo master a HG 10
UPDATE mysql_servers SET hostgroup_id=10 WHERE hostname='$SUCCESSOR_HOST';

-- Asegurar que cualquier otro nodo NO sea HG 10 (Solo un master a la vez)
UPDATE mysql_servers SET hostgroup_id=20 WHERE hostname!='$SUCCESSOR_HOST' AND hostgroup_id=10;

-- Asegurar que el nuevo master no esté en HG 20 (opcional, si queremos lecturas en master, dejarlo)
-- DELETE FROM mysql_servers WHERE hostname='$SUCCESSOR_HOST' AND hostgroup_id=20;

-- Cargar cambios
LOAD MYSQL SERVERS TO RUNTIME;
SAVE MYSQL SERVERS TO DISK;
EOF

echo "ProxySQL Updated successfully." >> /var/log/orchestrator-recovery.log
