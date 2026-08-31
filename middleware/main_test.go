package main

import (
	"encoding/json"
	"testing"
)

func TestOrderRequestDTO_Unmarshal(t *testing.T) {
	// Probar unmarshaling con formato unificado
	rawJSON := []byte(`{
		"order_id": "test-uuid-1",
		"event_id": 2,
		"event_name": "Festival de Jazz",
		"seat_id": 15,
		"seat_number": "A-15",
		"user_rut": "12.345.678-9",
		"price": 8500.5,
		"timestamp": "2026-08-30T22:00:00Z"
	}`)

	var req OrderRequest
	err := json.Unmarshal(rawJSON, &req)
	if err != nil {
		t.Fatalf("Error deserializando OrderRequest: %v", err)
	}

	if req.OrderID != "test-uuid-1" {
		t.Errorf("Esperaba order_id 'test-uuid-1', obtuvo '%s'", req.OrderID)
	}
	if req.EventID != 2 {
		t.Errorf("Esperaba event_id 2, obtuvo %d", req.EventID)
	}
	if req.UserRUT != 12345678 {
		t.Errorf("Esperaba user_rut 12345678, obtuvo %d", req.UserRUT)
	}
	if req.Price != 8500.5 {
		t.Errorf("Esperaba price 8500.5, obtuvo %f", req.Price)
	}
}

func TestOrderRequestDTO_LegacyFormat(t *testing.T) {
	// Probar compatibilidad con formato legacy de App3
	rawJSON := []byte(`{
		"event_id": "1",
		"user_id": "12345678",
		"quantity": 1
	}`)

	var req OrderRequest
	err := json.Unmarshal(rawJSON, &req)
	if err != nil {
		t.Fatalf("Error deserializando formato legacy: %v", err)
	}

	if req.EventID != 1 {
		t.Errorf("Esperaba event_id 1, obtuvo %d", req.EventID)
	}
	if req.UserRUT != 12345678 {
		t.Errorf("Esperaba user_rut 12345678, obtuvo %d", req.UserRUT)
	}
}

func TestGenerateUUID(t *testing.T) {
	uuid1 := generateUUID()
	uuid2 := generateUUID()
	if len(uuid1) != 36 {
		t.Errorf("Longitud inválida de UUID: %s", uuid1)
	}
	if uuid1 == uuid2 {
		t.Errorf("UUIDs generados deberían ser únicos: %s == %s", uuid1, uuid2)
	}
}
