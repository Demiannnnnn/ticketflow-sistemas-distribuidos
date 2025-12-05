# Usar una imagen base de Python
FROM python:3.9-slim


# Establecer el directorio de trabajo en el contenedor
WORKDIR /usr/src/app

# Copiar el archivo de dependencias y luego instalar las dependencias
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código de la aplicación
COPY . .

# Exponer el puerto en el que la aplicación se ejecuta dentro del contenedor
EXPOSE 5000

# Comando para ejecutar la aplicación
CMD ["python", "app.py"]
