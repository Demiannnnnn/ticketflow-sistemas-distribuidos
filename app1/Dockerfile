# Multi-stage build para optimizar el tamaño de la imagen

# Etapa 1: Build
FROM golang:1.21-alpine AS builder

WORKDIR /app

# Copiar archivos de dependencias
COPY backend/go.mod backend/go.sum ./
RUN go mod download

# Copiar código fuente
COPY backend/ ./

# Compilar la aplicación
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o main .

# Etapa 2: Runtime
FROM alpine:latest

RUN apk --no-cache add ca-certificates

WORKDIR /root/

# Copiar binario desde el builder
COPY --from=builder /app/main .

# Copiar frontend
COPY frontend/ ./frontend/
COPY static/ ./static/

# Exponer puerto
EXPOSE 8080

# Comando para ejecutar la aplicación
CMD ["./main"]
