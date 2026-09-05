package jobs

import (
	"bytes"
	"context"
	"log/slog"
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

func TestPublishWithoutRedisUsesHub(t *testing.T) {
	s := NewService(nil, nil, "", slog.Default())
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
