FROM mariadb:10.5

# Copiar el script de inicialización al directorio especial de la imagen
# Todo script .sql en este directorio se ejecuta al iniciar el contenedor por primera vez
COPY init.sql /docker-entrypoint-initdb.d/
