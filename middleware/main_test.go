package main

import (
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
)

func init() {
	gin.SetMode(gin.TestMode)
}

func postOrder(t *testing.T, publish Publisher, body string) *httptest.ResponseRecorder {
	t.Helper()
	router := setupRouter(publish)
	req := httptest.NewRequest(http.MethodPost, "/order", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	return w
}

func TestOrderPublicaYResponde200(t *testing.T) {
	var publicada *OrderRequest
	publish := func(o OrderRequest) error {
		publicada = &o
		return nil
	}

	w := postOrder(t, publish, `{"event_id":"3","user_id":"42","quantity":2}`)

	if w.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", w.Code, w.Body.String())
	}
	if publicada == nil || *publicada != (OrderRequest{EventID: "3", UserID: "42", Quantity: 2}) {
		t.Fatalf("orden publicada inesperada: %+v", publicada)
	}

	var resp struct {
		Message string       `json:"message"`
		Order   OrderRequest `json:"order"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatal(err)
	}
	if resp.Order.EventID != "3" || resp.Message == "" {
		t.Fatalf("respuesta inesperada: %+v", resp)
	}
}

func TestOrderRechazaDatosInvalidosSinPublicar(t *testing.T) {
	casos := map[string]string{
		"json malformado":   `{"event_id":`,
		"sin event_id":      `{"user_id":"1","quantity":1}`,
		"sin user_id":       `{"event_id":"1","quantity":1}`,
		"quantity cero":     `{"event_id":"1","user_id":"1","quantity":0}`,
		"quantity negativa": `{"event_id":"1","user_id":"1","quantity":-1}`,
		"quantity no int":   `{"event_id":"1","user_id":"1","quantity":"uno"}`,
		"event_id numérico": `{"event_id":1,"user_id":"1","quantity":1}`,
	}

	for nombre, body := range casos {
		t.Run(nombre, func(t *testing.T) {
			llamado := false
			w := postOrder(t, func(OrderRequest) error { llamado = true; return nil }, body)
			if w.Code != http.StatusBadRequest {
				t.Fatalf("status = %d, se esperaba 400", w.Code)
			}
			if llamado {
				t.Fatal("no debía publicarse una orden inválida")
			}
		})
	}
}

func TestOrderErrorAlPublicarDevuelve500SinFiltrarDetalle(t *testing.T) {
	w := postOrder(t, func(OrderRequest) error {
		return errors.New("amqp: dial tcp 10.0.0.5:5672: connection refused")
	}, `{"event_id":"1","user_id":"1","quantity":1}`)

	if w.Code != http.StatusInternalServerError {
		t.Fatalf("status = %d, se esperaba 500", w.Code)
	}
	if strings.Contains(w.Body.String(), "10.0.0.5") {
		t.Fatal("la respuesta no debe exponer el error interno")
	}
}

func TestPublishToRabbitMQSinBrokerDevuelveError(t *testing.T) {
	// Host no resoluble (TLD reservado .invalid): debe fallar con el error envuelto
	t.Setenv("RABBITMQ_HOST", "rabbitmq.invalid")
	err := publishToRabbitMQ(OrderRequest{EventID: "1", UserID: "1", Quantity: 1})
	if err == nil || !strings.Contains(err.Error(), "fallo al conectar a RabbitMQ") {
		t.Fatalf("error inesperado: %v", err)
	}
}
