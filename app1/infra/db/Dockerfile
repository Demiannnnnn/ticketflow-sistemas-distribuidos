FROM postgres:15

# Instalar dependencias de Python y herramientas necesarias
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Crear entorno virtual para evitar conflictos con paquetes del sistema
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Instalar Patroni y dependencias
RUN pip install patroni[etcd] psycopg2-binary

# Copiar configuración
COPY patroni.yml /etc/patroni.yml
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Cambiar al usuario postgres
USER postgres

# Exponer puertos: 5432 (Postgres), 8008 (Patroni API)
EXPOSE 5432 8008

ENTRYPOINT ["/entrypoint.sh"]
