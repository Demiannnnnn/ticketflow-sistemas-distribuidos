package main

import (
	"database/sql"
	"fmt"
	"log"
	"net/http"
	"os"
	"sync"
	"time"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	_ "github.com/lib/pq"
)

type Seat struct {
	ID         int        `json:"id"`
	EventID    int        `json:"event_id"`
	SeatNumber string     `json:"seat_number"`
	Status     string     `json:"status"` // available, reserved, sold
	ReservedAt *time.Time `json:"reserved_at,omitempty"`
	UserID     *int       `json:"user_id,omitempty"`
}

type Event struct {
	ID          int    `json:"id"`
	Name        string `json:"name"`
	Venue       string `json:"venue"`
	Date        string `json:"date"`
	TotalSeats  int    `json:"total_seats"`
	Description string `json:"description"`
}

type ReserveRequest struct {
	SeatID int `json:"seat_id" binding:"required"`
	UserID int `json:"user_id" binding:"required"`
}

var (
	db           *sql.DB
	seatMutex    sync.RWMutex
	instanceName string
)

func main() {
	instanceName = os.Getenv("INSTANCE_NAME")
	if instanceName == "" {
		instanceName = "app1-unknown"
	}

	// Conectar a PostgreSQL
	dbHost := os.Getenv("DB_HOST")
	if dbHost == "" {
		dbHost = "localhost"
	}
	dbUser := os.Getenv("DB_USER")
	if dbUser == "" {
		dbUser = "postgres"
	}
	dbPassword := os.Getenv("DB_PASSWORD")
	if dbPassword == "" {
		dbPassword = "postgres"
	}
	dbName := os.Getenv("DB_NAME")
	if dbName == "" {
		dbName = "ticketflow"
	}

	connStr := fmt.Sprintf("host=%s port=5432 user=%s password=%s dbname=%s sslmode=disable",
		dbHost, dbUser, dbPassword, dbName)

	var err error
	for i := 0; i < 30; i++ {
		db, err = sql.Open("postgres", connStr)
		if err == nil {
			err = db.Ping()
			if err == nil {
				log.Println("Conectado exitosamente a PostgreSQL")
				break
			}
		}
		log.Printf("Esperando conexión a base de datos... intento %d/30", i+1)
		time.Sleep(2 * time.Second)
	}

	if err != nil {
		log.Fatal("No se pudo conectar a la base de datos: ", err)
	}
	defer db.Close()

	// Inicializar base de datos
	initDB()

	// Configurar Gin
	router := gin.Default()

	// CORS
	router.Use(cors.New(cors.Config{
		AllowOrigins:     []string{"*"},
		AllowMethods:     []string{"GET", "POST", "PUT", "DELETE"},
		AllowHeaders:     []string{"Origin", "Content-Type"},
		ExposeHeaders:    []string{"Content-Length"},
		AllowCredentials: true,
		MaxAge:           12 * time.Hour,
	}))

	// Servir archivos estáticos (frontend)
	router.Static("/static", "./static")
	router.LoadHTMLGlob("frontend/*.html")

	// Ruta principal
	router.GET("/", func(c *gin.Context) {
		c.HTML(http.StatusOK, "index.html", nil)
	})

	// Health check
	router.GET("/health", healthCheck)

	// API Routes
	api := router.Group("/api")
	{
		api.GET("/events", getEvents)
		api.GET("/events/:id/seats", getSeats)
		api.POST("/reserve", reserveSeat)
		api.GET("/instance", getInstance)

		// Falta
		// 1.- POST /pay --> paySeat
		// 2.- POST /return --> returnSeat
		api.POST("/pay", paySeat)
		api.POST("/return", reserveSeat)
	}

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("App1 (%s) iniciando en puerto %s...", instanceName, port)
	router.Run(":" + port)
}

func initDB() {
	// Crear tabla de eventos
	_, err := db.Exec(`
		CREATE TABLE IF NOT EXISTS events (
			id SERIAL PRIMARY KEY,
			name VARCHAR(255) NOT NULL,
			venue VARCHAR(255) NOT NULL,
			date VARCHAR(100) NOT NULL,
			total_seats INT NOT NULL,
			description TEXT,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)
	`)
	if err != nil {
		log.Printf("Error creando tabla events: %v", err)
	}

	// Crear tabla de asientos
	_, err = db.Exec(`
		CREATE TABLE IF NOT EXISTS seats (
			id SERIAL PRIMARY KEY,
			event_id INT REFERENCES events(id),
			seat_number VARCHAR(50) NOT NULL,
			status VARCHAR(20) DEFAULT 'available',
			reserved_at TIMESTAMP,
			user_id INT,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			UNIQUE(event_id, seat_number)
		)
	`)
	if err != nil {
		log.Printf("Error creando tabla seats: %v", err)
	}

	// Crear índices para mejorar rendimiento
	db.Exec(`CREATE INDEX IF NOT EXISTS idx_seats_status ON seats(status)`)
	db.Exec(`CREATE INDEX IF NOT EXISTS idx_seats_event_id ON seats(event_id)`)

	// Insertar datos de ejemplo si no existen
	var count int
	db.QueryRow("SELECT COUNT(*) FROM events").Scan(&count)
	if count == 0 {
		insertSampleData()
	}
}

func insertSampleData() {
	// Insertar eventos de ejemplo
	events := []Event{
		{Name: "Concierto Rock Nacional", Venue: "Estadio Nacional", Date: "2025-12-15 20:00", TotalSeats: 50, Description: "Gran concierto de rock"},
		{Name: "Festival de Jazz", Venue: "Teatro Municipal", Date: "2025-12-20 19:00", TotalSeats: 30, Description: "Festival internacional de jazz"},
		{Name: "Partido de Fútbol", Venue: "Estadio Santa Laura", Date: "2025-12-25 18:00", TotalSeats: 40, Description: "Clásico del fútbol chileno"},
	}

	for _, event := range events {
		var eventID int
		err := db.QueryRow(`
			INSERT INTO events (name, venue, date, total_seats, description)
			VALUES ($1, $2, $3, $4, $5)
			RETURNING id`,
			event.Name, event.Venue, event.Date, event.TotalSeats, event.Description,
		).Scan(&eventID)

		if err != nil {
			log.Printf("Error insertando evento: %v", err)
			continue
		}

		// Crear asientos para cada evento
		for i := 1; i <= event.TotalSeats; i++ {
			seatNumber := fmt.Sprintf("A-%d", i)
			_, err := db.Exec(`
				INSERT INTO seats (event_id, seat_number, status)
				VALUES ($1, $2, 'available')`,
				eventID, seatNumber,
			)
			if err != nil {
				log.Printf("Error insertando asiento: %v", err)
			}
		}
	}
	log.Println("Datos de ejemplo insertados correctamente")
}

func healthCheck(c *gin.Context) {
	err := db.Ping()
	if err != nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"status":   "unhealthy",
			"instance": instanceName,
			"error":    err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"status":   "healthy",
		"instance": instanceName,
		"database": "connected",
	})
}

func getInstance(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"instance":  instanceName,
		"timestamp": time.Now().Format(time.RFC3339),
	})
}

func getEvents(c *gin.Context) {
	rows, err := db.Query(`
		SELECT e.id, e.name, e.venue, e.date, e.total_seats, e.description,
		       COUNT(CASE WHEN s.status = 'available' THEN 1 END) as available_seats
		FROM events e
		LEFT JOIN seats s ON e.id = s.event_id
		GROUP BY e.id, e.name, e.venue, e.date, e.total_seats, e.description
		ORDER BY e.date
	`)
	if err != nil {
		log.Printf("Error consultando eventos: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Error consultando eventos"})
		return
	}
	defer rows.Close()

	var events []map[string]interface{}
	for rows.Next() {
		var id, totalSeats, availableSeats int
		var name, venue, date, description string
		err := rows.Scan(&id, &name, &venue, &date, &totalSeats, &description, &availableSeats)
		if err != nil {
			log.Printf("Error escaneando evento: %v", err)
			continue
		}

		events = append(events, map[string]interface{}{
			"id":              id,
			"name":            name,
			"venue":           venue,
			"date":            date,
			"total_seats":     totalSeats,
			"description":     description,
			"available_seats": availableSeats,
		})
	}

	c.JSON(http.StatusOK, gin.H{
		"events":   events,
		"instance": instanceName,
	})
}

func getSeats(c *gin.Context) {
	eventID := c.Param("id")

	seatMutex.RLock()
	defer seatMutex.RUnlock()

	rows, err := db.Query(`
		SELECT id, event_id, seat_number, status, reserved_at, user_id
		FROM seats
		WHERE event_id = $1
		ORDER BY seat_number
	`, eventID)
	if err != nil {
		log.Printf("Error consultando asientos: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Error consultando asientos"})
		return
	}
	defer rows.Close()

	var seats []Seat
	for rows.Next() {
		var seat Seat
		err := rows.Scan(&seat.ID, &seat.EventID, &seat.SeatNumber, &seat.Status, &seat.ReservedAt, &seat.UserID)
		if err != nil {
			log.Printf("Error escaneando asiento: %v", err)
			continue
		}
		seats = append(seats, seat)
	}

	c.JSON(http.StatusOK, gin.H{
		"seats":    seats,
		"instance": instanceName,
	})
}

func reserveSeat(c *gin.Context) {
	var req ReserveRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Datos inválidos"})
		return
	}

	// SECCIÓN CRÍTICA: Evitar race conditions con mutex
	seatMutex.Lock()
	defer seatMutex.Unlock()

	// Iniciar transacción para garantizar consistencia
	tx, err := db.Begin()
	if err != nil {
		log.Printf("Error iniciando transacción: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Error en el sistema"})
		return
	}
	defer tx.Rollback()

	// Verificar que el asiento esté disponible
	var status string
	err = tx.QueryRow("SELECT status FROM seats WHERE id = $1 FOR UPDATE", req.SeatID).Scan(&status)
	if err != nil {
		log.Printf("Error consultando asiento: %v", err)
		c.JSON(http.StatusNotFound, gin.H{"error": "Asiento no encontrado"})
		return
	}

	if status != "available" {
		c.JSON(http.StatusConflict, gin.H{
			"error":  "Asiento no disponible",
			"status": status,
		})
		return
	}

	// Reservar el asiento
	now := time.Now()
	result, err := tx.Exec(`
		UPDATE seats
		SET status = 'reserved', reserved_at = $1, user_id = $2
		WHERE id = $3 AND status = 'available'
	`, now, req.UserID, req.SeatID)

	if err != nil {
		log.Printf("Error reservando asiento: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Error reservando asiento"})
		return
	}

	rowsAffected, _ := result.RowsAffected()
	if rowsAffected == 0 {
		c.JSON(http.StatusConflict, gin.H{"error": "El asiento ya fue reservado por otro usuario"})
		return
	}

	// Confirmar transacción
	if err := tx.Commit(); err != nil {
		log.Printf("Error confirmando transacción: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Error confirmando reserva"})
		return
	}

	log.Printf("[%s] Asiento %d reservado exitosamente por usuario %d", instanceName, req.SeatID, req.UserID)

	c.JSON(http.StatusOK, gin.H{
		"message":     "Asiento reservado exitosamente",
		"seat_id":     req.SeatID,
		"user_id":     req.UserID,
		"reserved_at": now.Format(time.RFC3339),
		"instance":    instanceName,
	})
}

func paySeat(c *gin.Context) {

}

func returnSeat(c *gin.Context) {

}
