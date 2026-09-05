package jobs

import (
	"bytes"
	"context"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/google/uuid"
)

func TestQueueFor(t *testing.T) {
	if queueFor("generate_3d") != QueueGenerate3D {
		t.Fatal("3d queue")
	}
	if queueFor("export") != QueueExport {
		t.Fatal("export queue")
	}
	if queueFor("generate_2d") != QueueGenerate2D {
		t.Fatal("2d queue")
	}
	if queueFor("other") != QueueGenerate2D {
		t.Fatal("default queue")
	}
}

func TestHubDeliversAndUnsubscribes(t *testing.T) {
	h := NewHub()
	ch, unsub := h.Subscribe("org:1")
	h.Publish("org:1", []byte(`{"event":"ping"}`))
	select {
	case msg := <-ch:
		if string(msg) != `{"event":"ping"}` {
			t.Fatalf("got %s", msg)
		}
	case <-time.After(time.Second):
		t.Fatal("timeout")
	}
	unsub()
	h.Publish("org:1", []byte(`{"event":"late"}`))
}

// TestPostAISendsInternalTokenHeader guards against the AI/worker service
// (services/ai, FastAPI) being callable — and therefore its GPU/Together-API
// pipeline runnable, bypassing the Go API's auth/quotas/rate-limiting
// entirely — by anyone who can merely reach its port. Every call the Go API
// makes into it MUST carry the shared X-Internal-Token header so the AI
// service (which validates it on its side) can reject unauthenticated
// callers.
func TestPostAISendsInternalTokenHeader(t *testing.T) {
	var gotToken, gotContentType, gotPath string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotToken = r.Header.Get("X-Internal-Token")
		gotContentType = r.Header.Get("Content-Type")
		gotPath = r.URL.Path
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{}`))
	}))
	defer srv.Close()

	s := NewService(nil, nil, srv.URL, "sekret-internal-token", slog.Default())
	resp, err := s.postAI(context.Background(), "/v1/pipeline", []byte(`{"brief":"x"}`))
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if gotToken != "sekret-internal-token" {
		t.Fatalf("X-Internal-Token = %q, want the configured internal token", gotToken)
	}
	if gotContentType != "application/json" {
		t.Fatalf("Content-Type = %q, want application/json", gotContentType)
	}
	if gotPath != "/v1/pipeline" {
		t.Fatalf("path = %q", gotPath)
	}
}

// TestPostAIOmitsHeaderWhenTokenUnset documents the (development-only)
// fallback behavior: an empty internal token — never valid in production per
// config.Validate — sends no header rather than an empty one, matching how
// checkInternal on the receiving side treats an empty configured token as
// "always reject".
func TestPostAIOmitsHeaderWhenTokenUnset(t *testing.T) {
	sawHeader := false
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, sawHeader = r.Header["X-Internal-Token"]
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	s := NewService(nil, nil, srv.URL, "", slog.Default())
	resp, err := s.postAI(context.Background(), "/v1/edit", []byte(`{}`))
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if sawHeader {
		t.Fatal("expected no X-Internal-Token header when the internal token is unset")
	}
}

func TestPublishWithoutRedisUsesHub(t *testing.T) {
	s := NewService(nil, nil, "", "", slog.Default())
	pid := uuid.New()
	oid := uuid.New()
	ch, unsub := s.ListenHub("org:" + oid.String())
	defer unsub()
	if err := s.Publish(context.Background(), pid, map[string]any{
		"event":  "job.updated",
		"org_id": oid.String(),
	}); err != nil {
		t.Fatal(err)
	}
	select {
	case msg := <-ch:
		if !bytes.Contains(msg, []byte("job.updated")) {
			t.Fatalf("got %s", msg)
		}
		if !bytes.Contains(msg, []byte(pid.String())) {
			t.Fatalf("missing project_id in %s", msg)
		}
	case <-time.After(time.Second):
		t.Fatal("timeout")
	}
}
