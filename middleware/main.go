package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/gin-gonic/gin"
	amqp "github.com/rabbitmq/amqp091-go"
)

// OrderRequest representa la estructura de una orden de compra
type OrderRequest struct {
	EventID  string `json:"event_id" binding:"required"`
	UserID   string `json:"user_id" binding:"required"`
	Quantity int    `json:"quantity" binding:"required"`
}

func main() {
	router := gin.Default()

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

	port := os.Getenv("PORT")
	if port == "" {
		port = "8000" // Puerto por defecto para el middleware
	}

	log.Printf("Middleware (Go) iniciando en puerto %s...", port)
	router.Run(":" + port)
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
		"",        // exchange
		q.Name,    // routing key
		false,     // mandatory
		false,     // immediate
		amqp.Publishing{
			ContentType: "application/json",
			Body:        body,
			DeliveryMode: amqp.Persistent,
		})
	if err != nil {
		return fmt.Errorf("fallo al publicar el mensaje: %w", err)
	}

	log.Printf(" [x] Enviada orden %s a la cola %s", body, queueName)
	return nil
}