package main

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	_ "github.com/lib/pq"
)

type Seat struct {
	ID                   int        `json:"id"`
	EventID              int        `json:"event_id"`
	SeatNumber           string     `json:"seat_number"`
	Status               string     `json:"status"` // available, reserved, sold
	ReservedAt           *time.Time `json:"reserved_at,omitempty"`
	ReservationExpiresAt *time.Time `json:"reservation_expires_at,omitempty"`
	UserID               *int       `json:"user_id,omitempty"`
}

type Event struct {
	ID             int    `json:"id"`
	Name           string `json:"name"`
	Venue          string `json:"venue"`
	Date           string `json:"date"`
	TotalSeats     int    `json:"total_seats"`
	AvailableSeats int    `json:"available_seats"`
	Description    string `json:"description"`
}

type ReserveRequest struct {
	SeatID int `json:"seat_id" binding:"required"`
	UserID int `json:"user_id" binding:"required"`
}

var (
	db           *sql.DB
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
		dbPassword = "postgres123"
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

	// Configurar Connection Pooling
	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(10)
	db.SetConnMaxLifetime(5 * time.Minute)

	// Inicializar base de datos con protección distribuida
	initDB()

	// Contexto para background workers
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Iniciar worker de limpieza de reservas expiradas
	go startReservationCleanupWorker(ctx, 10*time.Second)

	// Configurar Gin
	gin.SetMode(gin.ReleaseMode)
	router := gin.Default()

	// CORS
	router.Use(cors.New(cors.Config{
		AllowOrigins:     []string{"*"},
		AllowMethods:     []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowHeaders:     []string{"Origin", "Content-Type", "Accept"},
		ExposeHeaders:    []string{"Content-Length"},
		AllowCredentials: true,
		MaxAge:           12 * time.Hour,
	}))

	// Servir frontend si existe
	if _, err := os.Stat("frontend"); err == nil {
		router.LoadHTMLGlob("frontend/*.html")
		router.GET("/", func(c *gin.Context) {
			c.HTML(http.StatusOK, "index.html", nil)
		})
	}

	// Health check
	router.GET("/health", healthCheck)

	// API Routes
	api := router.Group("/api")
	{
		api.GET("/events", getEvents)
		api.GET("/events/:id", getEventByID)
		api.GET("/events/:id/seats", getSeats)
		api.POST("/reserve", reserveSeat)
		api.POST("/reserve/:id/confirm", confirmReservation)
		api.POST("/reserve/:id/cancel", cancelReservation)
		api.DELETE("/reserve/:id", cancelReservation)
		api.GET("/instance", getInstance)
	}

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	srv := &http.Server{
		Addr:    ":" + port,
		Handler: router,
	}

	go func() {
		log.Printf("App1 (%s) escuchando en puerto %s...", instanceName, port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Error en servidor HTTP App1: %v", err)
		}
	}()

	// Graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Apagando App1 de forma ordenada...")
	cancel()

	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer shutdownCancel()

	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Printf("Error durante el apagado HTTP: %v", err)
	}
	log.Println("App1 apagado correctamente.")
}

func initDB() {
	// Usar PostgreSQL advisory lock para evitar race condition entre réplicas al arrancar
	_, err := db.Exec(`SELECT pg_advisory_lock(987654321)`)
	if err != nil {
		log.Printf("Advertencia: No se pudo adquirir advisory lock: %v", err)
	} else {
		defer db.Exec(`SELECT pg_advisory_unlock(987654321)`)
	}

	// Crear tabla de eventos
	_, err = db.Exec(`
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

	// Crear tabla de asientos con columna reservation_expires_at
	_, err = db.Exec(`
		CREATE TABLE IF NOT EXISTS seats (
			id SERIAL PRIMARY KEY,
			event_id INT REFERENCES events(id) ON DELETE CASCADE,
			seat_number VARCHAR(50) NOT NULL,
			status VARCHAR(20) DEFAULT 'available',
			reserved_at TIMESTAMP,
			reservation_expires_at TIMESTAMP,
			user_id INT,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			UNIQUE(event_id, seat_number)
		)
	`)
	if err != nil {
		log.Printf("Error creando tabla seats: %v", err)
	}

	// Migración segura de columna si la tabla ya existía
	db.Exec(`ALTER TABLE seats ADD COLUMN IF NOT EXISTS reservation_expires_at TIMESTAMP`)

	// Crear índices para mejorar rendimiento
	db.Exec(`CREATE INDEX IF NOT EXISTS idx_seats_status ON seats(status)`)
	db.Exec(`CREATE INDEX IF NOT EXISTS idx_seats_event_id ON seats(event_id)`)
	db.Exec(`CREATE INDEX IF NOT EXISTS idx_seats_expires ON seats(reservation_expires_at) WHERE status = 'reserved'`)

	// Insertar datos de ejemplo si no existen
	var count int
	db.QueryRow("SELECT COUNT(*) FROM events").Scan(&count)
	if count == 0 {
		insertSampleData()
	}
}

func insertSampleData() {
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

		for i := 1; i <= event.TotalSeats; i++ {
			seatNumber := fmt.Sprintf("A-%d", i)
			_, err := db.Exec(`
				INSERT INTO seats (event_id, seat_number, status)
				VALUES ($1, $2, 'available')
				ON CONFLICT (event_id, seat_number) DO NOTHING`,
				eventID, seatNumber,
			)
			if err != nil {
				log.Printf("Error insertando asiento: %v", err)
			}
		}
	}
	log.Println("Datos de ejemplo insertados correctamente")
}

// startReservationCleanupWorker libera periódicamente reservas expiradas
func startReservationCleanupWorker(ctx context.Context, interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	log.Println("[Worker] Iniciado worker de expiración de reservas")
	for {
		select {
		case <-ctx.Done():
			log.Println("[Worker] Deteniendo worker de expiración de reservas")
			return
		case <-ticker.C:
			result, err := db.Exec(`
				UPDATE seats
				SET status = 'available', user_id = NULL, reserved_at = NULL, reservation_expires_at = NULL
				WHERE status = 'reserved' 
				  AND reservation_expires_at IS NOT NULL 
				  AND reservation_expires_at < NOW()
			`)
			if err != nil {
				log.Printf("[Worker] Error liberando reservas expiradas: %v", err)
			} else {
				if rows, _ := result.RowsAffected(); rows > 0 {
					log.Printf("[Worker] [✓] Se liberaron %d reservas expiradas", rows)
				}
			}
		}
	}
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

	var events []Event
	for rows.Next() {
		var ev Event
		err := rows.Scan(&ev.ID, &ev.Name, &ev.Venue, &ev.Date, &ev.TotalSeats, &ev.Description, &ev.AvailableSeats)
		if err != nil {
			log.Printf("Error escaneando evento: %v", err)
			continue
		}
		events = append(events, ev)
	}

	c.JSON(http.StatusOK, gin.H{
		"events":   events,
		"instance": instanceName,
	})
}

func getEventByID(c *gin.Context) {
	idParam := c.Param("id")
	eventID, err := strconv.Atoi(idParam)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "ID de evento inválido"})
		return
	}

	var ev Event
	err = db.QueryRow(`
		SELECT e.id, e.name, e.venue, e.date, e.total_seats, e.description,
		       COUNT(CASE WHEN s.status = 'available' THEN 1 END) as available_seats
		FROM events e
		LEFT JOIN seats s ON e.id = s.event_id
		WHERE e.id = $1
		GROUP BY e.id, e.name, e.venue, e.date, e.total_seats, e.description
	`, eventID).Scan(&ev.ID, &ev.Name, &ev.Venue, &ev.Date, &ev.TotalSeats, &ev.Description, &ev.AvailableSeats)

	if err == sql.ErrNoRows {
		c.JSON(http.StatusNotFound, gin.H{"error": "Evento no encontrado"})
		return
	} else if err != nil {
		log.Printf("Error consultando evento por ID: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Error consultando evento"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"event":    ev,
		"instance": instanceName,
	})
}

func getSeats(c *gin.Context) {
	idParam := c.Param("id")
	eventID, err := strconv.Atoi(idParam)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "ID de evento inválido"})
		return
	}

	rows, err := db.Query(`
		SELECT id, event_id, seat_number, status, reserved_at, reservation_expires_at, user_id
		FROM seats
		WHERE event_id = $1
		ORDER BY id
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
		err := rows.Scan(&seat.ID, &seat.EventID, &seat.SeatNumber, &seat.Status, &seat.ReservedAt, &seat.ReservationExpiresAt, &seat.UserID)
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
		c.JSON(http.StatusBadRequest, gin.H{"error": "Datos inválidos: " + err.Error()})
		return
	}

	// Iniciar transacción de base de datos para bloqueo de fila distribuido
	tx, err := db.Begin()
	if err != nil {
		log.Printf("Error iniciando transacción: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Error en el sistema"})
		return
	}
	defer tx.Rollback()

	// Bloqueo pesimista a nivel de fila (PostgreSQL SELECT ... FOR UPDATE)
	var status string
	err = tx.QueryRow("SELECT status FROM seats WHERE id = $1 FOR UPDATE", req.SeatID).Scan(&status)
	if err == sql.ErrNoRows {
		c.JSON(http.StatusNotFound, gin.H{"error": "Asiento no encontrado"})
		return
	} else if err != nil {
		log.Printf("Error consultando asiento: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Error en base de datos"})
		return
	}

	if status != "available" {
		c.JSON(http.StatusConflict, gin.H{
			"error":  "Asiento no disponible",
			"status": status,
		})
		return
	}

	// Reservar por 10 minutos
	now := time.Now()
	expiresAt := now.Add(10 * time.Minute)

	result, err := tx.Exec(`
		UPDATE seats
		SET status = 'reserved', reserved_at = $1, reservation_expires_at = $2, user_id = $3
		WHERE id = $4 AND status = 'available'
	`, now, expiresAt, req.UserID, req.SeatID)

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

	if err := tx.Commit(); err != nil {
		log.Printf("Error confirmando transacción: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Error confirmando reserva"})
		return
	}

	log.Printf("[%s] Asiento %d reservado exitosamente por usuario %d (expira en %s)",
		instanceName, req.SeatID, req.UserID, expiresAt.Format(time.RFC3339))

	c.JSON(http.StatusOK, gin.H{
		"message":                "Asiento reservado exitosamente",
		"seat_id":                req.SeatID,
		"user_id":                req.UserID,
		"reserved_at":            now.Format(time.RFC3339),
		"reservation_expires_at": expiresAt.Format(time.RFC3339),
		"instance":               instanceName,
	})
}

func confirmReservation(c *gin.Context) {
	idParam := c.Param("id")
	seatID, err := strconv.Atoi(idParam)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "ID de asiento inválido"})
		return
	}

	tx, err := db.Begin()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Error en el sistema"})
		return
	}
	defer tx.Rollback()

	var status string
	err = tx.QueryRow("SELECT status FROM seats WHERE id = $1 FOR UPDATE", seatID).Scan(&status)
	if err == sql.ErrNoRows {
		c.JSON(http.StatusNotFound, gin.H{"error": "Asiento no encontrado"})
		return
	} else if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Error en base de datos"})
		return
	}

	if status != "reserved" {
		c.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("Solo asientos en estado 'reserved' pueden confirmarse. Estado actual: %s", status)})
		return
	}

	_, err = tx.Exec(`
		UPDATE seats
		SET status = 'sold', reservation_expires_at = NULL
		WHERE id = $1
	`, seatID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Error confirmando venta de asiento"})
		return
	}

	if err := tx.Commit(); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Error al confirmar transacción"})
		return
	}

	log.Printf("[%s] Asiento %d confirmado como VENDIDO", instanceName, seatID)
	c.JSON(http.StatusOK, gin.H{
		"message": "Asiento confirmado y vendido exitosamente",
		"seat_id": seatID,
		"status":  "sold",
	})
}

func cancelReservation(c *gin.Context) {
	idParam := c.Param("id")
	seatID, err := strconv.Atoi(idParam)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "ID de asiento inválido"})
		return
	}

	tx, err := db.Begin()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Error en el sistema"})
		return
	}
	defer tx.Rollback()

	result, err := tx.Exec(`
		UPDATE seats
		SET status = 'available', user_id = NULL, reserved_at = NULL, reservation_expires_at = NULL
		WHERE id = $1 AND status = 'reserved'
	`, seatID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Error cancelando reserva"})
		return
	}

	rowsAffected, _ := result.RowsAffected()
	if rowsAffected == 0 {
		c.JSON(http.StatusNotFound, gin.H{"error": "Asiento no encontrado o no estaba en estado reservado"})
		return
	}

	if err := tx.Commit(); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Error al confirmar cancelación"})
		return
	}

	log.Printf("[%s] Reserva de asiento %d cancelada/liberada", instanceName, seatID)
	c.JSON(http.StatusOK, gin.H{
		"message": "Reserva cancelada exitosamente, asiento disponible",
		"seat_id": seatID,
		"status":  "available",
	})
}

