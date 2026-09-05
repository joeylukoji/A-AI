package planschema_test

import (
	"encoding/json"
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

func TestSchemasAreValidJSON(t *testing.T) {
	_, file, _, _ := runtime.Caller(0)
	dir := filepath.Dir(file)
	for _, name := range []string{"building-spec.schema.json", "plan-document.schema.json", "compliance.schema.json"} {
		b, err := os.ReadFile(filepath.Join(dir, name))
		if err != nil {
			t.Fatal(err)
		}
		var v any
		if err := json.Unmarshal(b, &v); err != nil {
			t.Fatalf("%s: %v", name, err)
		}
	}
}

func TestSamplePlanDocumentMatchesRequiredKeys(t *testing.T) {
	sample := map[string]any{
		"version": "1.0",
		"units":   "m",
		"floor": map[string]any{
			"level": 0, "height_m": 2.7,
			"bounds": map[string]any{"width": 10.0, "depth": 8.0},
		},
		"walls": []any{},
		"rooms": []any{},
	}
	for _, k := range []string{"version", "units", "floor", "walls", "rooms"} {
		if _, ok := sample[k]; !ok {
			t.Fatalf("missing %s", k)
		}
	}
}
