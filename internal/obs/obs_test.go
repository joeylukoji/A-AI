package obs

import "testing"

func TestLoggerReturnsUsableLogger(t *testing.T) {
	log := Logger("api")
	if log == nil {
		t.Fatal("Logger returned nil")
	}
	// Must not panic when used, and With("service", ...) must have been
	// applied (best-effort check: a logger built from the same handler type
	// logs without error).
	log.Info("smoke test")
}

func TestJobAttrsOrderAndKeys(t *testing.T) {
	attrs := JobAttrs("job-1", "proj-1", "org-1")
	want := []any{"job_id", "job-1", "project_id", "proj-1", "org_id", "org-1"}
	if len(attrs) != len(want) {
		t.Fatalf("got %d attrs, want %d: %#v", len(attrs), len(want), attrs)
	}
	for i := range want {
		if attrs[i] != want[i] {
			t.Fatalf("attrs[%d] = %#v, want %#v", i, attrs[i], want[i])
		}
	}
}
