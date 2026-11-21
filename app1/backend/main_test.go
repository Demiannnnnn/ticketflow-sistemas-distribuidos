package main

import (
	"database/sql"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/DATA-DOG/go-sqlmock"
	"github.com/gin-gonic/gin"
)

func init() {
	gin.SetMode(gin.TestMode)
}

// setup reemplaza la conexión global por un sqlmock y arma las rutas de la API
func setup(t *testing.T) (*gin.Engine, sqlmock.Sqlmock) {
	t.Helper()
	mockDB, mock, err := sqlmock.New(sqlmock.MonitorPingsOption(true))
	if err != nil {
		t.Fatal(err)
	}
	prev := db
	db = mockDB
	instanceName = "app1-test"
	t.Cleanup(func() {
		if err := mock.ExpectationsWereMet(); err != nil {
			t.Errorf("expectativas SQL no cumplidas: %v", err)
		}
		mockDB.Close()
		db = prev
	})

	r := gin.New()
	r.GET("/health", healthCheck)
	r.GET("/api/events", getEvents)
	r.GET("/api/events/:id/seats", getSeats)
	r.POST("/api/reserve", reserveSeat)
	r.GET("/api/instance", getInstance)
	return r, mock
}

func do(r *gin.Engine, method, path, body string) (*httptest.ResponseRecorder, map[string]any) {
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	var out map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &out)
	return w, out
}

const (
	qSelectSeat = `SELECT status FROM seats WHERE id = \$1 FOR UPDATE`
	qUpdateSeat = `UPDATE seats\s+SET status = 'reserved', reserved_at = \$1, user_id = \$2\s+WHERE id = \$3 AND status = 'available'`
)

func TestReserveSeatDisponible(t *testing.T) {
	r, mock := setup(t)
	mock.ExpectBegin()
	mock.ExpectQuery(qSelectSeat).WithArgs(7).WillReturnRows(sqlmock.NewRows([]string{"status"}).AddRow("available"))
	mock.ExpectExec(qUpdateSeat).WithArgs(sqlmock.AnyArg(), 42, 7).WillReturnResult(sqlmock.NewResult(0, 1))
	mock.ExpectCommit()

	w, body := do(r, http.MethodPost, "/api/reserve", `{"seat_id":7,"user_id":42}`)

	if w.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", w.Code, w.Body.String())
	}
	if body["seat_id"] != float64(7) || body["user_id"] != float64(42) || body["instance"] != "app1-test" {
		t.Fatalf("respuesta inesperada: %v", body)
	}
	if _, err := time.Parse(time.RFC3339, body["reserved_at"].(string)); err != nil {
		t.Fatalf("reserved_at no es RFC3339: %v", err)
	}
}

func TestReserveSeatYaReservadoDevuelve409YHaceRollback(t *testing.T) {
	r, mock := setup(t)
	mock.ExpectBegin()
	mock.ExpectQuery(qSelectSeat).WithArgs(7).WillReturnRows(sqlmock.NewRows([]string{"status"}).AddRow("reserved"))
	mock.ExpectRollback()

	w, body := do(r, http.MethodPost, "/api/reserve", `{"seat_id":7,"user_id":42}`)

	if w.Code != http.StatusConflict || body["status"] != "reserved" {
		t.Fatalf("status = %d, body = %v", w.Code, body)
	}
}

func TestReserveSeatCarreraEntreReplicasDevuelve409(t *testing.T) {
	// Otra réplica ganó la carrera entre el SELECT y el UPDATE: 0 filas afectadas
	r, mock := setup(t)
	mock.ExpectBegin()
	mock.ExpectQuery(qSelectSeat).WithArgs(7).WillReturnRows(sqlmock.NewRows([]string{"status"}).AddRow("available"))
	mock.ExpectExec(qUpdateSeat).WithArgs(sqlmock.AnyArg(), 42, 7).WillReturnResult(sqlmock.NewResult(0, 0))
	mock.ExpectRollback()

	w, body := do(r, http.MethodPost, "/api/reserve", `{"seat_id":7,"user_id":42}`)

	if w.Code != http.StatusConflict || !strings.Contains(body["error"].(string), "otro usuario") {
		t.Fatalf("status = %d, body = %v", w.Code, body)
	}
}

func TestReserveSeatInexistenteDevuelve404(t *testing.T) {
	r, mock := setup(t)
	mock.ExpectBegin()
	mock.ExpectQuery(qSelectSeat).WithArgs(999).WillReturnError(sql.ErrNoRows)
	mock.ExpectRollback()

	w, _ := do(r, http.MethodPost, "/api/reserve", `{"seat_id":999,"user_id":1}`)
	if w.Code != http.StatusNotFound {
		t.Fatalf("status = %d", w.Code)
	}
}

func TestReserveSeatErrorAlActualizarDevuelve500(t *testing.T) {
	r, mock := setup(t)
	mock.ExpectBegin()
	mock.ExpectQuery(qSelectSeat).WithArgs(7).WillReturnRows(sqlmock.NewRows([]string{"status"}).AddRow("available"))
	mock.ExpectExec(qUpdateSeat).WillReturnError(errors.New("conexión perdida"))
	mock.ExpectRollback()

	w, _ := do(r, http.MethodPost, "/api/reserve", `{"seat_id":7,"user_id":42}`)
	if w.Code != http.StatusInternalServerError {
		t.Fatalf("status = %d", w.Code)
	}
}

func TestReserveSeatErrorAlIniciarTransaccionDevuelve500(t *testing.T) {
	r, mock := setup(t)
	mock.ExpectBegin().WillReturnError(errors.New("sin conexión"))

	w, _ := do(r, http.MethodPost, "/api/reserve", `{"seat_id":7,"user_id":42}`)
	if w.Code != http.StatusInternalServerError {
		t.Fatalf("status = %d", w.Code)
	}
}

func TestReserveSeatDatosInvalidosNoTocanLaBD(t *testing.T) {
	r, _ := setup(t)
	for _, body := range []string{`{}`, `{"seat_id":7}`, `{"user_id":1}`, `{"seat_id":"siete","user_id":1}`, `no-json`} {
		w, _ := do(r, http.MethodPost, "/api/reserve", body)
		if w.Code != http.StatusBadRequest {
			t.Errorf("body %s: status = %d, se esperaba 400", body, w.Code)
		}
	}
}

func TestGetEventsIncluyeAsientosDisponibles(t *testing.T) {
	r, mock := setup(t)
	rows := sqlmock.NewRows([]string{"id", "name", "venue", "date", "total_seats", "description", "available_seats"}).
		AddRow(1, "Concierto", "Estadio", "2025-12-15 20:00", 50, "Rock", 48).
		AddRow(2, "Jazz", "Teatro", "2025-12-20 19:00", 30, "Festival", 30)
	mock.ExpectQuery(`SELECT e.id, e.name`).WillReturnRows(rows)

	w, body := do(r, http.MethodGet, "/api/events", "")

	if w.Code != http.StatusOK {
		t.Fatalf("status = %d", w.Code)
	}
	events := body["events"].([]any)
	if len(events) != 2 {
		t.Fatalf("se esperaban 2 eventos, hay %d", len(events))
	}
	first := events[0].(map[string]any)
	if first["available_seats"] != float64(48) || first["name"] != "Concierto" {
		t.Fatalf("evento inesperado: %v", first)
	}
}

func TestGetEventsErrorDeBDDevuelve500(t *testing.T) {
	r, mock := setup(t)
	mock.ExpectQuery(`SELECT e.id, e.name`).WillReturnError(errors.New("db caída"))

	w, _ := do(r, http.MethodGet, "/api/events", "")
	if w.Code != http.StatusInternalServerError {
		t.Fatalf("status = %d", w.Code)
	}
}

func TestGetSeatsDevuelveAsientosDelEvento(t *testing.T) {
	r, mock := setup(t)
	now := time.Now()
	rows := sqlmock.NewRows([]string{"id", "event_id", "seat_number", "status", "reserved_at", "user_id"}).
		AddRow(1, 3, "A-1", "available", nil, nil).
		AddRow(2, 3, "A-2", "reserved", now, 42)
	mock.ExpectQuery(`SELECT id, event_id, seat_number, status, reserved_at, user_id\s+FROM seats\s+WHERE event_id = \$1`).
		WithArgs("3").WillReturnRows(rows)

	w, _ := do(r, http.MethodGet, "/api/events/3/seats", "")
	if w.Code != http.StatusOK {
		t.Fatalf("status = %d", w.Code)
	}

	var resp struct {
		Seats []Seat `json:"seats"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatal(err)
	}
	if len(resp.Seats) != 2 {
		t.Fatalf("se esperaban 2 asientos: %+v", resp.Seats)
	}
	if resp.Seats[0].UserID != nil || resp.Seats[0].ReservedAt != nil {
		t.Fatalf("asiento libre no debe tener usuario ni fecha: %+v", resp.Seats[0])
	}
	if resp.Seats[1].UserID == nil || *resp.Seats[1].UserID != 42 || resp.Seats[1].Status != "reserved" {
		t.Fatalf("asiento reservado inesperado: %+v", resp.Seats[1])
	}
}

func TestHealthCheck(t *testing.T) {
	r, mock := setup(t)
	mock.ExpectPing()
	w, body := do(r, http.MethodGet, "/health", "")
	if w.Code != http.StatusOK || body["status"] != "healthy" {
		t.Fatalf("status = %d, body = %v", w.Code, body)
	}

	mock.ExpectPing().WillReturnError(errors.New("db caída"))
	w, body = do(r, http.MethodGet, "/health", "")
	if w.Code != http.StatusServiceUnavailable || body["status"] != "unhealthy" {
		t.Fatalf("status = %d, body = %v", w.Code, body)
	}
}

func TestGetInstance(t *testing.T) {
	r, _ := setup(t)
	w, body := do(r, http.MethodGet, "/api/instance", "")
	if w.Code != http.StatusOK || body["instance"] != "app1-test" {
		t.Fatalf("status = %d, body = %v", w.Code, body)
	}
}
