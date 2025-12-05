#!/bin/sh

echo "Iniciando configuración de replicación de MariaDB y Orchestrator..."

DB_ROOT_PASS="***REMOVED***" # Ajustar según .env
REPL_USER="repl_user"
REPL_PASS="repl_password"

wait_for_db() {
    host=$1
    echo "Esperando a que $host esté listo..."
    until mysqladmin ping -h "$host" -u root -p"$DB_ROOT_PASS" --silent 2>/dev/null; do
        echo "Esperando a $host..."
        sleep 2
    done
    echo "$host está listo."
}

wait_for_db "app2_db1"
wait_for_db "app2_db2"
wait_for_db "app2_db3"

# Obtener posición del master
echo "INFO: Obteniendo posición del master (DB1)..."
MASTER_STATUS=$(mysql --host=app2_db1 -uroot -p$DB_ROOT_PASS -e "SHOW MASTER STATUS\G" 2>/dev/null)
MASTER_LOG_FILE=$(echo "$MASTER_STATUS" | grep "File:" | awk '{print $2}')
MASTER_LOG_POS=$(echo "$MASTER_STATUS" | grep "Position:" | awk '{print $2}')

if [ -z "$MASTER_LOG_FILE" ] || [ -z "$MASTER_LOG_POS" ]; then
    echo "ERROR: No se pudo obtener el estado del master. Usando valores por defecto."
    MASTER_LOG_FILE="mariadb-bin.000001"
    MASTER_LOG_POS=4
fi

echo "INFO: Master Log File: $MASTER_LOG_FILE, Position: $MASTER_LOG_POS"

# Configurar DB2 para seguir a DB1
echo "INFO: Configurando DB2 para seguir a DB1..."
mysql --host=app2_db2 -uroot -p$DB_ROOT_PASS <<-EOSQL 2>/dev/null
    STOP SLAVE;
    RESET SLAVE ALL;
    CHANGE MASTER TO 
        MASTER_HOST='app2_db1',
        MASTER_USER='$REPL_USER',
        MASTER_PASSWORD='$REPL_PASS',
        MASTER_PORT=3306,
        MASTER_LOG_FILE='$MASTER_LOG_FILE',
        MASTER_LOG_POS=$MASTER_LOG_POS;
    START SLAVE;
EOSQL

if [ $? -eq 0 ]; then
    echo "SUCCESS: DB2 configurado como esclavo de DB1."
else
    echo "ERROR: Falló la configuración de DB2."
fi

# Configurar DB3 para seguir a DB1
echo "INFO: Configurando DB3 para seguir a DB1..."
mysql --host=app2_db3 -uroot -p$DB_ROOT_PASS <<-EOSQL 2>/dev/null
    STOP SLAVE;
    RESET SLAVE ALL;
    CHANGE MASTER TO 
        MASTER_HOST='app2_db1',
        MASTER_USER='$REPL_USER',
        MASTER_PASSWORD='$REPL_PASS',
        MASTER_PORT=3306,
        MASTER_LOG_FILE='$MASTER_LOG_FILE',
        MASTER_LOG_POS=$MASTER_LOG_POS;
    START SLAVE;
EOSQL

if [ $? -eq 0 ]; then
    echo "SUCCESS: DB3 configurado como esclavo de DB1."
else
    echo "ERROR: Falló la configuración de DB3."
fi

# Esperar un poco para que la replicación se inicie
sleep 3

echo "INFO: Verificando estado de replicación..."
echo "--- DB2 Replication Status ---"
mysql --host=app2_db2 -uroot -p$DB_ROOT_PASS -e "SHOW SLAVE STATUS\G" 2>/dev/null | grep -E "Slave_IO_Running|Slave_SQL_Running|Slave_SQL_Running_State"

echo "--- DB3 Replication Status ---"
mysql --host=app2_db3 -uroot -p$DB_ROOT_PASS -e "SHOW SLAVE STATUS\G" 2>/dev/null | grep -E "Slave_IO_Running|Slave_SQL_Running|Slave_SQL_Running_State"

echo "INFO: Descubriendo topología en Orchestrator..."
# Orchestrator necesita que le "descubramos" al menos un nodo para escanear el resto
if command -v orchestrator-client >/dev/null 2>&1; then
    orchestrator-client -c discover -i app2_db1:3306 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "SUCCESS: Nodo db1 descubierto por Orchestrator."
    else
        echo "WARNING: Falló el descubrimiento de db1 por Orchestrator (puede ser normal si Orchestrator aún no está listo)."
    fi
else
    echo "WARNING: orchestrator-client no encontrado, saltando descubrimiento."
fi

echo "¡Configuración de Cluster HA Finalizada!"
