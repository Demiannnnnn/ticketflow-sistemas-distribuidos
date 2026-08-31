FROM openarkcode/orchestrator:v3.2.4

# Instalar cliente MySQL para ejecutar comandos contra ProxySQL
USER root
RUN apk add --no-cache mysql-client sqlite

# Copiar configuración y scripts
COPY orchestrator.conf.json /etc/orchestrator.conf.json
COPY scripts/ /scripts/

# Dar permisos de ejecución a los scripts
RUN chmod +x /scripts/*.sh

USER 0
