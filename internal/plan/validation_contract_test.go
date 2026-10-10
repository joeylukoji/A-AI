package plan

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"testing"
)

type fixtureChange struct {
	Path   []any           `json:"path"`
	Value  json.RawMessage `json:"value"`
	Remove bool            `json:"remove"`
}

func TestSharedValidationContract(t *testing.T) {
	raw, err := os.ReadFile("../../packages/plan-schema/validation-cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var fixtures struct {
		Base  json.RawMessage `json:"base"`
		Cases []struct {
			ID      string          `json:"id"`
			Code    *string         `json:"code"`
			Changes []fixtureChange `json:"changes"`
		} `json:"cases"`
	}
	if err := json.Unmarshal(raw, &fixtures); err != nil {
		t.Fatal(err)
	}
	for _, fixture := range fixtures.Cases {
		t.Run(fixture.ID, func(t *testing.T) {
			document := decodeFixture(t, fixtures.Base)
			for _, change := range fixture.Changes {
				document = applyFixtureChange(t, document, change)
			}
			encoded, err := json.Marshal(document)
			if err != nil {
				t.Fatal(err)
			}
			before := bytes.Clone(encoded)
			err = Validate(encoded)
			if !bytes.Equal(before, encoded) {
				t.Fatal("validation mutated the input")
			}
			if fixture.Code == nil {
				if err != nil {
					t.Fatal(err)
				}
				return
			}
			var violation *ValidationError
			if !errors.As(err, &violation) {
				t.Fatalf("expected %s, got %v", *fixture.Code, err)
			}
			if violation.Code != *fixture.Code {
				t.Fatalf("expected %s, got %s", *fixture.Code, violation.Code)
			}
		})
	}
}

func decodeFixture(t *testing.T, raw []byte) any {
	t.Helper()
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	var value any
	if err := decoder.Decode(&value); err != nil {
		t.Fatal(err)
	}
	return value
}

func applyFixtureChange(t *testing.T, document any, change fixtureChange) any {
	t.Helper()
	if len(change.Path) == 0 {
		return decodeFixture(t, change.Value)
	}
	parent := document
	for _, component := range change.Path[:len(change.Path)-1] {
		switch key := component.(type) {
		case string:
			parent = parent.(map[string]any)[key]
		case float64:
			parent = parent.([]any)[int(key)]
		default:
			t.Fatalf("unsupported fixture path: %v", component)
		}
	}
	last := change.Path[len(change.Path)-1]
	if change.Remove {
		delete(parent.(map[string]any), last.(string))
		return document
	}
	value := decodeFixture(t, change.Value)
	switch key := last.(type) {
	case string:
		parent.(map[string]any)[key] = value
	case float64:
		parent.([]any)[int(key)] = value
	default:
		t.Fatalf("unsupported fixture path: %v", last)
	}
	return document
}

func TestValidateRejectsMalformedJSON(t *testing.T) {
	for _, raw := range []string{"", "{", "{} {}", "{\"x\":NaN}"} {
		var violation *ValidationError
		if err := Validate([]byte(raw)); !errors.As(err, &violation) || violation.Code != "invalid_json" {
			t.Errorf("expected invalid_json for %q, got %v", raw, err)
		}
	}
}

func FuzzValidateNeverPanics(f *testing.F) {
	f.Add([]byte(`{"version":"1.0","units":"m"}`))
	f.Add([]byte(`null`))
	f.Fuzz(func(t *testing.T, raw []byte) {
		_ = Validate(raw)
	})
}

// Set PLAN_BENCHMARK_RUN to check Python-produced documents at the Go save boundary.
// This opt-in integration check never makes the ordinary suite depend on local runs.
func TestGeneratedBenchmarkDocuments(t *testing.T) {
	run := os.Getenv("PLAN_BENCHMARK_RUN")
	if run == "" {
		t.Skip("PLAN_BENCHMARK_RUN not set")
	}
	pattern := filepath.Join(run, "cases", "*", "*", "*", "document.json")
	paths, err := filepath.Glob(pattern)
	if err != nil || len(paths) == 0 {
		t.Fatalf("no benchmark documents at %q: %v", run, err)
	}
	for _, path := range paths {
		raw, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		if err := Validate(raw); err != nil {
			t.Errorf("%s: %v", path, err)
		}
	}
	t.Logf("validated %d generated documents (including warmups)", len(paths))
}

func TestGeometryComplexityLimit(t *testing.T) {
	raw, err := os.ReadFile("../../packages/plan-schema/validation-cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var fixtures struct {
		Base map[string]any `json:"base"`
	}
	if err := json.Unmarshal(raw, &fixtures); err != nil {
		t.Fatal(err)
	}
	for _, size := range []struct{ rooms, vertices int }{{65, 4}, {1, 65}, {5, 52}} {
		t.Run(fmt.Sprintf("rooms-%d-vertices-%d", size.rooms, size.vertices), func(t *testing.T) {
			polygon := make([]map[string]float64, 0, size.vertices)
			for index := 0; index < size.vertices; index++ {
				angle := 2 * math.Pi * float64(index) / float64(size.vertices)
				polygon = append(polygon, map[string]float64{"x": 2 + math.Cos(angle), "y": 2 + math.Sin(angle)})
			}
			rooms := make([]map[string]any, 0, size.rooms)
			for index := 0; index < size.rooms; index++ {
				rooms = append(rooms, map[string]any{"id": fmt.Sprintf("r%d", index), "polygon": polygon})
			}
			fixtures.Base["rooms"] = rooms
			encoded, err := json.Marshal(fixtures.Base)
			if err != nil {
				t.Fatal(err)
			}
			var violation *ValidationError
			if err := Validate(encoded); !errors.As(err, &violation) || violation.Code != "geometry_complexity_limit" {
				t.Fatalf("expected geometry_complexity_limit, got %v", err)
			}
		})
	}
}
