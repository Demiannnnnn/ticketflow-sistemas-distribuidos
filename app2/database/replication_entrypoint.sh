#!/bin/bash
set -e

# Si soy el slave, esperar al master y configurar replicación
if [ "$MARIADB_ROLE" = "slave" ]; then
    echo "Waiting for Master to be ready..."
    until mysql -h mariadb_master -u root -p"$MYSQL_ROOT_PASSWORD" -e "SELECT 1"; do
        sleep 2
    done

    echo "Configuring replication..."
    mysql -u root -p"$MYSQL_ROOT_PASSWORD" -e "CHANGE MASTER TO MASTER_HOST='mariadb_master', MASTER_USER='replicator', MASTER_PASSWORD='replicator_password', MASTER_LOG_FILE='mariadb-bin.000001', MASTER_LOG_POS=0;"
    mysql -u root -p"$MYSQL_ROOT_PASSWORD" -e "START SLAVE;"
    
    echo "Replication configured."
fi

# Ejecutar el comando original (docker-entrypoint.sh mysqld)
exec /usr/local/bin/docker-entrypoint.sh mysqld