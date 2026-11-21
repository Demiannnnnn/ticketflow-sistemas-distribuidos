#!/bin/bash

# Obtener IP del contenedor
export IP=$(hostname -i)

# Reemplazar variables en patroni.yml
sed -i "s/{{name}}/$PATRONI_NAME/g" /etc/patroni.yml
sed -i "s/{{ip}}/$IP/g" /etc/patroni.yml
sed -i "s/{{superuser_password}}/${PATRONI_SUPERUSER_PASSWORD:-$DB_PASSWORD}/g" /etc/patroni.yml
sed -i "s/{{replication_password}}/${PATRONI_REPLICATION_PASSWORD:-$REPLICATION_PASSWORD}/g" /etc/patroni.yml

# Iniciar Patroni
exec patroni /etc/patroni.yml
