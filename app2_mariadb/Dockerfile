FROM mariadb:10.5

# Copiar scripts de inicialización al directorio especial de la imagen
# Todo script .sh o .sql en este directorio se ejecuta al iniciar el contenedor por primera vez
COPY init_cluster.sh /docker-entrypoint-initdb.d/01_init_cluster.sh
COPY init.sql /docker-entrypoint-initdb.d/02_init_app.sql
RUN chmod +x /docker-entrypoint-initdb.d/01_init_cluster.sh
