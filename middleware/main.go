package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"time"

	"github.com/gin-gonic/gin"
	amqp "github.com/rabbitmq/amqp091-go"
)

func startTCPServer() {
	// Escuchar en un puerto diferente al de Gin
	listener, err := net.Listen("tcp", ":8001")
	if err != nil {
		log.Fatalf("Error al iniciar TCP listener: %v", err)
	}
	defer listener.Close()

	log.Println("Servidor TCP (JSON) escuchando en :8001")

	for {
		conn, err := listener.Accept()
		if err != nil {
			log.Printf("Error aceptando conexión TCP: %v", err)
			continue
		}
		// Manejar la conexión en una goroutine separada
		go handleTCPConnection(conn)
	}
}

type TicketPayload struct {
	SeatID  string `json:"seat_id"`
	EventID string `json:"event_id"` // O string, según tu base de datos
	Price   int    `json:"price"`
	UserRut int    `json:"user_rut"`
}

// Estructura contenedora (el mensaje completo)
type NotificationMessage struct {
	EventName string        `json:"event"` // Corresponde al primer argumento "TICKET_PAID"
	Data      TicketPayload `json:"data"`  // Corresponde al diccionario/objeto
}

func handleTCPConnection(conn net.Conn) {
	defer conn.Close()

	// 1. DECODIFICAR
	decoder := json.NewDecoder(conn)
	var msg NotificationMessage

	if err := decoder.Decode(&msg); err != nil {
		log.Printf("Error decodificando TCP: %v", err)
		return
	}

	log.Printf("TCP recibido: Evento=%s, Rut=%s", msg.EventName, msg.Data.UserRut)

	// 2. ENRUTAMIENTO (ROUTING)
	var targetPath string

	switch msg.EventName {
	case "TICKET_PAID":
		targetPath = "/api/pay"
	case "TICKET_REFUNDED":
		targetPath = "/api/return"
	default:
		log.Printf("Evento desconocido: %s. Ignorando.", msg.EventName)
		conn.Write([]byte("ERROR: Unknown Event"))
		return
	}

	// 3. ENVIAR POST AL DESTINO SELECCIONADO
	// Llamamos a una función auxiliar para no repetir código
	err := sendPostToNginx(targetPath, msg.Data)

	if err != nil {
		log.Printf("Fallo al reenviar a %s: %v", targetPath, err)
		conn.Write([]byte("ERROR: Upstream Failed"))
	} else {
		conn.Write([]byte("ACK"))
	}
}

// Función auxiliar para enviar el POST
func sendPostToNginx(path string, payload interface{}) error {
	// A. Construir URL (Nginx es el host)
	targetURL := fmt.Sprintf("http://nginx%s", path)

	// B. Serializar el payload (solo los datos, sin el envoltorio del evento)
	jsonData, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("error marshalling: %v", err)
	}

	// C. Crear Request
	req, err := http.NewRequest("POST", targetURL, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("error creando request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")

	// D. Enviar
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("error de red: %v", err)
	}
	defer resp.Body.Close()

	// E. Verificar estado HTTP (esperamos 200 o 201)
	if resp.StatusCode >= 400 {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("nginx respondió con error %d: %s", resp.StatusCode, string(bodyBytes))
	}

	log.Printf("Reenvío exitoso a %s (Status: %d)", targetURL, resp.StatusCode)
	return nil
}

// OrderRequest representa la estructura de una orden de compra
type OrderRequest struct {
	EventID  string `json:"event_id" binding:"required"`
	UserID   string `json:"user_id" binding:"required"`
	Quantity int    `json:"quantity" binding:"required"`
}

func main() {
	router := gin.Default()

	go startTCPServer()

	// Endpoint para recibir órdenes de compra desde App3
	router.POST("/order", func(c *gin.Context) {
		var req OrderRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		// Publicar la orden en RabbitMQ
		err := publishToRabbitMQ(req)
		if err != nil {
			log.Printf("Error publicando orden en RabbitMQ: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Error interno al procesar la orden"})
			return
		}

		c.JSON(http.StatusOK, gin.H{"message": "Orden recibida y enviada a la cola de procesamiento", "order": req})
	})

	// Endpoint a desarrollar
	// GET "http://nginx/api/events" from App3
	router.GET("/events", func(c *gin.Context) {
		// Reescribimos la URL para que al enviarla a Nginx sea correcta
		c.Request.URL.Path = "/api/events"
		proxyHandler(c)
	})

	// Handler normal
	router.GET("/api/events", proxyHandler)

	// Lo mismo para el POST /reserve
	router.POST("/reserve", func(c *gin.Context) {
		c.Request.URL.Path = "/api/reserve"
		proxyHandler(c)
	})
	router.POST("/api/reserve", proxyHandler)

	router.POST("/ticket", ticketToTickets)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8000" // Puerto por defecto para el middleware
	}

	log.Printf("Middleware (Go) iniciando en puerto %s...", port)
	router.Run(":" + port)
}

// ----------------------------------------------------
// FUNCIÓN HANDLER DEL PROXY
// ----------------------------------------------------

// TargetBaseURL es la URL base del servidor de destino (Nginx en tu caso).
const TargetBaseURL = "http://nginx"

// proxyHandler reenvía la petición entrante (GET o POST) al servidor de destino.
func proxyHandler(c *gin.Context) {
	// Construimos la URL final usando el Path que (posiblemente) modificamos arriba
	// TargetBaseURL es "http://nginx"
	targetURL := fmt.Sprintf("%s%s", TargetBaseURL, c.Request.URL.Path)

	// Si hay query params (ej ?id=1), los agregamos
	if c.Request.URL.RawQuery != "" {
		targetURL += "?" + c.Request.URL.RawQuery
	}

	log.Printf("Reenviando a: %s", targetURL) // Log para depurar

	proxyReq, err := http.NewRequestWithContext(c.Request.Context(), c.Request.Method, targetURL, c.Request.Body)
	// ... (resto de la lógica de headers y client.Do)

	// 3. Copiar Headers (¡IMPORTANTE: NO copiar el Host!)
	for k, v := range c.Request.Header {
		proxyReq.Header[k] = v
	}
	// ELIMINA ESTA LÍNEA QUE TENÍAS ANTES:
	// proxyReq.Header.Set("Host", c.Request.Host)

	// OPCIONAL: Forzar el Host correcto si Nginx es muy estricto
	// proxyReq.Header.Set("Host", "nginx")

	// 4. Ejecutar petición
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(proxyReq)
	if err != nil {
		log.Printf("Error conectando con Nginx: %v", err)
		c.JSON(http.StatusBadGateway, gin.H{"error": "No se pudo conectar al servicio de eventos"})
		return
	}
	defer resp.Body.Close()

	// 5. Devolver respuesta
	c.Status(resp.StatusCode)
	for k, v := range resp.Header {
		c.Writer.Header()[k] = v
	}
	io.Copy(c.Writer, resp.Body)
}

func publishToRabbitMQ(order OrderRequest) error {
	rabbitmqHost := os.Getenv("RABBITMQ_HOST")
	if rabbitmqHost == "" {
		rabbitmqHost = "localhost" // Valor por defecto si no está en las variables de entorno
	}
	rabbitmqURL := fmt.Sprintf("amqp://guest:guest@%s:5672/", rabbitmqHost)

	conn, err := amqp.Dial(rabbitmqURL)
	if err != nil {
		return fmt.Errorf("fallo al conectar a RabbitMQ: %w", err)
	}
	defer conn.Close()

	ch, err := conn.Channel()
	if err != nil {
		return fmt.Errorf("fallo al abrir un canal: %w", err)
	}
	defer ch.Close()

	queueName := "orden_creada" // Coincide con la cola que espera App3

	q, err := ch.QueueDeclare(
		queueName, // name
		true,      // durable
		false,     // delete when unused
		false,     // exclusive
		false,     // no-wait
		nil,       // arguments
	)
	if err != nil {
		return fmt.Errorf("fallo al declarar la cola: %w", err)
	}

	body, err := json.Marshal(order)
	if err != nil {
		return fmt.Errorf("fallo al serializar la orden: %w", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	err = ch.PublishWithContext(ctx,
		"",     // exchange
		q.Name, // routing key
		false,  // mandatory
		false,  // immediate
		amqp.Publishing{
			ContentType:  "application/json",
			Body:         body,
			DeliveryMode: amqp.Persistent,
		})
	if err != nil {
		return fmt.Errorf("fallo al publicar el mensaje: %w", err)
	}

	log.Printf(" [x] Enviada orden %s a la cola %s", body, queueName)
	return nil
}

func ticketToTickets(c *gin.Context) {

	// puerto 6002 host app2_nginx

}
