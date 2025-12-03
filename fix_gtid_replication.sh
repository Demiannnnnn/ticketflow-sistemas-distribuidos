#!/bin/sh

DB_ROOT_PASS="***REMOVED***"
REPL_USER="repl_user"
REPL_PASS="repl_password"

echo "--- Iniciando reparación de replicación GTID ---"

fix_slave() {
    SLAVE_HOST=$1
    MASTER_HOST="db1"
    
    echo "Reparando $SLAVE_HOST..."
    
    # 1. Detener esclavo
    mysql -h "$SLAVE_HOST" -u root -p"$DB_ROOT_PASS" -e "STOP SLAVE;"
    
    # 2. Resetear estado GTID local (OJO: Esto borra datos locales si no están en el master, pero en setup inicial es lo correcto)
    # RESET MASTER borra el historial de GTID propio del nodo
    mysql -h "$SLAVE_HOST" -u root -p"$DB_ROOT_PASS" -e "RESET MASTER;"
    
    # 3. Resetear configuración de esclavo
    mysql -h "$SLAVE_HOST" -u root -p"$DB_ROOT_PASS" -e "RESET SLAVE;"
    
    # 4. Reconfigurar apuntando al master db1
    mysql -h "$SLAVE_HOST" -u root -p"$DB_ROOT_PASS" -e "CHANGE MASTER TO MASTER_HOST='$MASTER_HOST', MASTER_USER='$REPL_USER', MASTER_PASSWORD='$REPL_PASS', MASTER_PORT=3306, MASTER_USE_GTID=slave_pos;"
    
    # 5. Iniciar esclavo
    mysql -h "$SLAVE_HOST" -u root -p"$DB_ROOT_PASS" -e "START SLAVE;"
    
    # 6. Verificar
    echo "Estado de $SLAVE_HOST:"
    mysql -h "$SLAVE_HOST" -u root -p"$DB_ROOT_PASS" -e "SHOW SLAVE STATUS\G" | grep "Slave_.*_Running"
}

fix_slave "db2"
fix_slave "db3"

echo "--- Reparación completada. Verifica en Orchestrator ---"
