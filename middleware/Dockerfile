# Etapa 1: Build
FROM golang:1.21-alpine AS builder

WORKDIR /app

# Copiar archivos de dependencias y descargar dependencias
COPY go.mod go.sum ./

# Copiar código fuente
COPY . .

RUN go mod tidy
RUN go mod download

# Compilar la aplicación
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o middleware .

# Etapa 2: Runtime
FROM alpine:latest

# Añadir certificados de CA para permitir conexiones HTTPS/TLS
RUN apk --no-cache add ca-certificates

WORKDIR /root/

# Copiar el binario compilado desde la etapa de build
COPY --from=builder /app/middleware .

# Exponer el puerto en el que correrá la aplicación
EXPOSE 8000

# Comando para ejecutar la aplicación
CMD ["./middleware"]
