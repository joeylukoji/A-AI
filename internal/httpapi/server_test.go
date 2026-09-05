package httpapi

import (
	"encoding/json"
	"html/template"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"
	"testing/fstest"

	"github.com/a-ai/a-ai/internal/config"
)

func TestHealthz(t *testing.T) {
	tmpl := template.Must(template.New("x").Parse(`{{define "landing.html"}}ok{{end}}`))
	static := fstest.MapFS{"app.css": &fstest.MapFile{Data: []byte("body{}")}}
	cfg := config.Config{InternalToken: "tok", AppEnv: "test"}
	log := slog.New(slog.NewTextHandler(io.Discard, nil))
	srv := New(cfg, log, nil, nil, nil, nil, nil, nil, nil, tmpl, static)

	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	rr := httptest.NewRecorder()
	srv.Handler().ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("status %d", rr.Code)
	}
	var body map[string]string
	if err := json.Unmarshal(rr.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body["status"] != "ok" {
		t.Fatalf("body %#v", body)
	}
}

func TestWantsJSON(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/api/v1/me", nil)
	if !wantsJSON(req) {
		t.Fatal("api path should want json")
	}
	req = httptest.NewRequest(http.MethodGet, "/projects", nil)
	req.Header.Set("Accept", "application/json")
	if !wantsJSON(req) {
		t.Fatal("accept json should want json")
	}
}
