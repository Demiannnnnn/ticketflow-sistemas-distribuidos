#!/bin/bash

# Obtener IP del contenedor
export IP=$(hostname -i)

# Reemplazar variables en patroni.yml
sed -i "s/{{name}}/$PATRONI_NAME/g" /etc/patroni.yml
sed -i "s/{{ip}}/$IP/g" /etc/patroni.yml

# Iniciar Patroni
exec patroni /etc/patroni.yml
