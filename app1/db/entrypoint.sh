#!/bin/bash

# Obtener IP del contenedor
export IP=$(hostname -i)

# Reemplazar variables en patroni.yml
sed -i "s/{{name}}/$PATRONI_NAME/g" /etc/patroni.yml
sed -i "s/{{ip}}/$IP/g" /etc/patroni.yml

# Fix permissions for the data directory
chown -R postgres:postgres /var/lib/postgresql/data/patroni

# Iniciar Patroni as postgres user
exec su postgres -c "patroni /etc/patroni.yml"
