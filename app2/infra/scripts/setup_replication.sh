#!/bin/sh

echo "Iniciando configuración de replicación de MariaDB y Orchestrator..."

DB_ROOT_PASS="root_password" # Ajustar según .env
REPL_USER="repl_user"
REPL_PASS="repl_password"

wait_for_db() {
    host=$1
    echo "Esperando a que $host esté listo..."
    until mysqladmin ping -h "$host" -u root -p"$DB_ROOT_PASS" --silent; do
        echo "Esperando a $host..."
        sleep 2
    done
    echo "$host está listo."
}

wait_for_db "app2_db1"
wait_for_db "app2_db2"
wait_for_db "app2_db3"

# Configurar DB2 para seguir a DB1
echo "INFO: Configurando DB2 para seguir a DB1..."
mysql --host=app2_db2 -uroot -p$DB_ROOT_PASS -e "STOP SLAVE; RESET MASTER; CHANGE MASTER TO MASTER_HOST='app2_db1', MASTER_USER='$REPL_USER', MASTER_PASSWORD='$REPL_PASS', MASTER_PORT=3306, MASTER_USE_GTID=slave_pos; START SLAVE;"
if [ $? -eq 0 ]; then
    echo "SUCCESS: DB2 configurado como esclavo de DB1."
else
    echo "ERROR: Falló la configuración de DB2."
fi

# Configurar DB3 para seguir a DB1
echo "INFO: Configurando DB3 para seguir a DB1..."
mysql --host=app2_db3 -uroot -p$DB_ROOT_PASS -e "STOP SLAVE; RESET MASTER; CHANGE MASTER TO MASTER_HOST='app2_db1', MASTER_USER='$REPL_USER', MASTER_PASSWORD='$REPL_PASS', MASTER_PORT=3306, MASTER_USE_GTID=slave_pos; START SLAVE;"
if [ $? -eq 0 ]; then
    echo "SUCCESS: DB3 configurado como esclavo de DB1."
else
    echo "ERROR: Falló la configuración de DB3."
fi

echo "INFO: Verificando estado de replicación (ejecutando SHOW SLAVE STATUS en DB2 y DB3)..."
echo "--- DB2 Replication Status ---"
mysql --host=app2_db2 -uroot -p$DB_ROOT_PASS -e "SHOW SLAVE STATUS\G" | grep "Slave_IO_Running\|Slave_SQL_Running"
echo "--- DB3 Replication Status ---"
mysql --host=app2_db3 -uroot -p$DB_ROOT_PASS -e "SHOW SLAVE STATUS\G" | grep "Slave_IO_Running\|Slave_SQL_Running"

echo "INFO: Descubriendo topología en Orchestrator..."
# Orchestrator necesita que le "descubramos" al menos un nodo para escanear el resto
orchestrator-client -c discover -i app2_db1:3306
if [ $? -eq 0 ]; then
    echo "SUCCESS: Nodo db1 descubierto por Orchestrator."
else
    echo "ERROR: Falló el descubrimiento de db1 por Orchestrator."
fi

echo "¡Configuración de Cluster HA Finalizada!"
