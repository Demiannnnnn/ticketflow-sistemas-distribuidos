package main

import (
	"bufio"
	"context"
	"crypto/rand"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	amqp "github.com/rabbitmq/amqp091-go"
)

// OrderRequest representa la estructura unificada de una orden de compra
type OrderRequest struct {
	OrderID    string  `json:"order_id"`
	EventID    int     `json:"event_id"`
	EventName  string  `json:"event_name"`
	SeatID     int     `json:"seat_id"`
	SeatNumber string  `json:"seat_number"`
	UserRUT    int     `json:"user_rut"`
	Price      float64 `json:"price"`
	Timestamp  string  `json:"timestamp"`

	// Retrocompatibilidad con campos legacy
	LegacyEventID string `json:"event_id_str,omitempty"`
	LegacyUserID  string `json:"user_id,omitempty"`
	LegacyQty     int    `json:"quantity,omitempty"`
}

// UnmarshalJSON permite parsear órdenes tanto en formato estricto como legacy
func (o *OrderRequest) UnmarshalJSON(data []byte) error {
	type Alias OrderRequest
	aux := &struct {
		RawEventID interface{} `json:"event_id"`
		RawUserRUT interface{} `json:"user_rut"`
		RawUserID  interface{} `json:"user_id"`
		RawPrice   interface{} `json:"price"`
		*Alias
	}{
		Alias: (*Alias)(o),
	}

	if err := json.Unmarshal(data, &aux); err != nil {
		return err
	}

	// Parsear EventID si viene como int o string
	if aux.RawEventID != nil {
		switch v := aux.RawEventID.(type) {
		case float64:
			o.EventID = int(v)
		case string:
			if id, err := strconv.Atoi(v); err == nil {
				o.EventID = id
			}
		}
	}

	// Parsear UserRUT si viene como user_rut o user_id (int o string)
	targetRUT := aux.RawUserRUT
	if targetRUT == nil {
		targetRUT = aux.RawUserID
	}
	if targetRUT != nil {
		switch v := targetRUT.(type) {
		case float64:
			o.UserRUT = int(v)
		case string:
			str := v
			if idx := strings.Index(str, "-"); idx != -1 {
				str = str[:idx]
			}
			clean := ""
			for _, r := range str {
				if r >= '0' && r <= '9' {
					clean += string(r)
				}
			}
			if rut, err := strconv.Atoi(clean); err == nil {
				o.UserRUT = rut
			}
		}
	}

	// Parsear Price si viene como float, int o string
	if aux.RawPrice != nil {
		switch v := aux.RawPrice.(type) {
		case float64:
			o.Price = v
		case string:
			if p, err := strconv.ParseFloat(v, 64); err == nil {
				o.Price = p
			}
		}
	}

	return nil
}

func generateUUID() string {
	b := make([]byte, 16)
	_, _ = io.ReadFull(rand.Reader, b)
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:])
}

// RabbitMQClient gestiona la conexión persistente con RabbitMQ (evita Connection Thrashing)
type RabbitMQClient struct {
	mu        sync.Mutex
	url       string
	queueName string
	conn      *amqp.Connection
	ch        *amqp.Channel
	connected bool
}

func NewRabbitMQClient(host, queueName string) *RabbitMQClient {
	if host == "" {
		host = "rabbitmq"
	}
	url := fmt.Sprintf("amqp://guest:guest@%s:5672/", host)
	return &RabbitMQClient{
		url:       url,
		queueName: queueName,
	}
}

func (r *RabbitMQClient) Connect() error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if r.connected && r.conn != nil && !r.conn.IsClosed() && r.ch != nil && !r.ch.IsClosed() {
		return nil
	}

	log.Printf("[RabbitMQ] Conectando a %s...", r.url)
	conn, err := amqp.Dial(r.url)
	if err != nil {
		r.connected = false
		return fmt.Errorf("fallo al conectar a RabbitMQ: %w", err)
	}

	ch, err := conn.Channel()
	if err != nil {
		conn.Close()
		r.connected = false
		return fmt.Errorf("fallo al abrir canal RabbitMQ: %w", err)
	}

	_, err = ch.QueueDeclare(
		r.queueName,
		true,  // durable
		false, // delete when unused
		false, // exclusive
		false, // no-wait
		nil,   // arguments
	)
	if err != nil {
		ch.Close()
		conn.Close()
		r.connected = false
		return fmt.Errorf("fallo al declarar cola %s: %w", r.queueName, err)
	}

	r.conn = conn
	r.ch = ch
	r.connected = true
	log.Printf("[RabbitMQ] Conexión establecida exitosamente (Cola: %s)", r.queueName)
	return nil
}

func (r *RabbitMQClient) Publish(order OrderRequest) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if !r.connected || r.ch == nil || r.ch.IsClosed() {
		// Reintento de reconexión
		if err := r.reconnectUnlocked(); err != nil {
			return fmt.Errorf("RabbitMQ no está disponible: %w", err)
		}
	}

	body, err := json.Marshal(order)
	if err != nil {
		return fmt.Errorf("fallo al serializar orden: %w", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	err = r.ch.PublishWithContext(ctx,
		"",          // exchange
		r.queueName, // routing key
		false,       // mandatory
		false,       // immediate
		amqp.Publishing{
			ContentType:  "application/json",
			DeliveryMode: amqp.Persistent,
			Body:         body,
		},
	)
	if err != nil {
		r.connected = false
		return fmt.Errorf("error publicando mensaje en RabbitMQ: %w", err)
	}

	log.Printf("[RabbitMQ] [✓] Orden publicada en cola '%s': %s", r.queueName, string(body))
	return nil
}

func (r *RabbitMQClient) reconnectUnlocked() error {
	if r.conn != nil && !r.conn.IsClosed() {
		r.conn.Close()
	}
	conn, err := amqp.Dial(r.url)
	if err != nil {
		r.connected = false
		return err
	}
	ch, err := conn.Channel()
	if err != nil {
		conn.Close()
		r.connected = false
		return err
	}
	_, err = ch.QueueDeclare(r.queueName, true, false, false, false, nil)
	if err != nil {
		ch.Close()
		conn.Close()
		r.connected = false
		return err
	}
	r.conn = conn
	r.ch = ch
	r.connected = true
	return nil
}

func (r *RabbitMQClient) IsConnected() bool {
	r.mu.Lock()
	defer r.mu.Unlock()
	return r.connected && r.conn != nil && !r.conn.IsClosed()
}

func (r *RabbitMQClient) Close() {
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.ch != nil {
		r.ch.Close()
	}
	if r.conn != nil {
		r.conn.Close()
	}
	r.connected = false
}

// startNotificationListener inicia el listener TCP en el puerto 7002 para recibir callbacks de App2
func startNotificationListener(ctx context.Context, port string) {
	listener, err := net.Listen("tcp", ":"+port)
	if err != nil {
		log.Printf("[TCP Listener] Error iniciando listener en :%s: %v", port, err)
		return
	}
	defer listener.Close()

	log.Printf("[TCP Listener] Escuchando notificaciones de App2 en puerto :%s...", port)

	go func() {
		<-ctx.Done()
		listener.Close()
	}()

	for {
		conn, err := listener.Accept()
		if err != nil {
			select {
			case <-ctx.Done():
				return
			default:
				log.Printf("[TCP Listener] Error aceptando conexión: %v", err)
				continue
			}
		}

		go handleNotificationConnection(conn)
	}
}

func handleNotificationConnection(conn net.Conn) {
	defer conn.Close()
	scanner := bufio.NewScanner(conn)
	for scanner.Scan() {
		line := scanner.Text()
		if len(line) == 0 {
			continue
		}

		var payload struct {
			Type      string                 `json:"type"`
			Data      map[string]interface{} `json:"data"`
			Timestamp string                 `json:"timestamp"`
		}

		if err := json.Unmarshal([]byte(line), &payload); err != nil {
			log.Printf("[TCP Listener] [!] Error decodificando notificación: %s", line)
			continue
		}

		log.Printf("[TCP Listener] [★ NOTIFICACIÓN RECIBIDA] Tipo: %s | Datos: %+v | Timestamp: %s",
			payload.Type, payload.Data, payload.Timestamp)
	}
}

func main() {
	rabbitmqHost := os.Getenv("RABBITMQ_HOST")
	if rabbitmqHost == "" {
		rabbitmqHost = "rabbitmq"
	}
	queueName := "orden_creada"
	rmqClient := NewRabbitMQClient(rabbitmqHost, queueName)

	// Intentar conectar al inicio en segundo plano con reintentos
	go func() {
		for i := 1; i <= 30; i++ {
			if err := rmqClient.Connect(); err == nil {
				break
			}
			log.Printf("[RabbitMQ] Esperando a RabbitMQ... intento %d/30", i)
			time.Sleep(3 * time.Second)
		}
	}()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Iniciar listener TCP de notificaciones de retorno
	notifyPort := os.Getenv("NOTIFY_PORT")
	if notifyPort == "" {
		notifyPort = "7002"
	}
	go startNotificationListener(ctx, notifyPort)

	// Configurar API HTTP con Gin
	gin.SetMode(gin.ReleaseMode)
	router := gin.Default()

	router.GET("/health", func(c *gin.Context) {
		if rmqClient.IsConnected() {
			c.JSON(http.StatusOK, gin.H{
				"status":   "healthy",
				"service":  "middleware",
				"rabbitmq": "connected",
			})
		} else {
			c.JSON(http.StatusServiceUnavailable, gin.H{
				"status":   "degraded",
				"service":  "middleware",
				"rabbitmq": "disconnected",
			})
		}
	})

	router.POST("/order", func(c *gin.Context) {
		var req OrderRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "JSON inválido: " + err.Error()})
			return
		}

		// Completar valores por defecto y normalizar DTO
		if req.OrderID == "" {
			req.OrderID = generateUUID()
		}
		if req.Timestamp == "" {
			req.Timestamp = time.Now().UTC().Format(time.RFC3339)
		}
		if req.Price <= 0 {
			req.Price = 5000.0
		}
		if req.EventName == "" {
			req.EventName = fmt.Sprintf("Evento #%d", req.EventID)
		}

		if req.UserRUT == 0 {
			c.JSON(http.StatusBadRequest, gin.H{"error": "user_rut es obligatorio"})
			return
		}

		// Publicar en RabbitMQ usando la conexión persistente
		if err := rmqClient.Publish(req); err != nil {
			log.Printf("[Middleware] Error publicando orden: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Error interno al encolar orden: " + err.Error()})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"message":  "Orden recibida y enviada a la cola de procesamiento",
			"order_id": req.OrderID,
			"order":    req,
		})
	})

	httpPort := os.Getenv("PORT")
	if httpPort == "" {
		httpPort = "8000"
	}

	srv := &http.Server{
		Addr:    ":" + httpPort,
		Handler: router,
	}

	go func() {
		log.Printf("Middleware (Go) escuchando HTTP en puerto :%s...", httpPort)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Error en servidor HTTP: %v", err)
		}
	}()

	// Graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Apagando Middleware de forma ordenada...")
	cancel()

	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer shutdownCancel()

	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Printf("Error durante el apagado HTTP: %v", err)
	}

	rmqClient.Close()
	log.Println("Middleware apagado correctamente.")
}