package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
)

func TestSeatStruct(t *testing.T) {
	now := time.Now().UTC()
	exp := now.Add(10 * time.Minute)
	userID := 12345678

	seat := Seat{
		ID:                   1,
		EventID:              2,
		SeatNumber:           "A-10",
		Status:               "reserved",
		ReservedAt:           &now,
		ReservationExpiresAt: &exp,
		UserID:               &userID,
	}

	data, err := json.Marshal(seat)
	if err != nil {
		t.Fatalf("Error serializando Seat: %v", err)
	}

	var parsed Seat
	err = json.Unmarshal(data, &parsed)
	if err != nil {
		t.Fatalf("Error deserializando Seat: %v", err)
	}

	if parsed.SeatNumber != "A-10" || parsed.Status != "reserved" || *parsed.UserID != 12345678 {
		t.Errorf("Seat parsed incorrect: %+v", parsed)
	}
}

func TestEventStruct(t *testing.T) {
	ev := Event{
		ID:             1,
		Name:           "Concierto Rock Nacional",
		Venue:          "Estadio Nacional",
		Date:           "2026-12-15 20:00",
		TotalSeats:     50,
		AvailableSeats: 45,
		Description:    "Concierto en vivo",
	}

	data, err := json.Marshal(ev)
	if err != nil {
		t.Fatalf("Error serializando Event: %v", err)
	}

	var parsed Event
	if err := json.Unmarshal(data, &parsed); err != nil {
		t.Fatalf("Error deserializando Event: %v", err)
	}

	if parsed.Name != ev.Name || parsed.AvailableSeats != 45 {
		t.Errorf("Event parsed incorrect: %+v", parsed)
	}
}

func TestGetInstanceEndpoint(t *testing.T) {
	gin.SetMode(gin.TestMode)
	router := gin.New()
	instanceName = "test-instance-1"
	router.GET("/api/instance", getInstance)

	req, _ := http.NewRequest(http.MethodGet, "/api/instance", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Esperaba código 200, obtuvo %d", w.Code)
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["instance"] != "test-instance-1" {
		t.Errorf("Esperaba instance 'test-instance-1', obtuvo '%v'", resp["instance"])
	}
}

func TestReserveValidation(t *testing.T) {
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.POST("/api/reserve", reserveSeat)

	// Petición con cuerpo inválido (sin user_id)
	invalidBody := bytes.NewBufferString(`{"seat_id": 5}`)
	req, _ := http.NewRequest(http.MethodPost, "/api/reserve", invalidBody)
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("Esperaba Bad Request (400), obtuvo %d", w.Code)
	}
}
