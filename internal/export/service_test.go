package export

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func samplePlan() *PlanDocument {
	raw := []byte(`{
	  "version":"1.0","units":"m",
	  "floor":{"level":0,"height_m":2.7,"bounds":{"width":10,"depth":8}},
	  "walls":[
	    {"id":"w1","a":{"x":0,"y":0},"b":{"x":10,"y":0},"thickness_m":0.2},
	    {"id":"w2","a":{"x":10,"y":0},"b":{"x":10,"y":8},"thickness_m":0.2}
	  ],
	  "rooms":[{"id":"r1","name":"Séjour","type":"living","polygon":[
	    {"x":0,"y":0},{"x":5,"y":0},{"x":5,"y":4},{"x":0,"y":4}
	  ]}],
	  "openings":[]
	}`)
	doc, err := Parse(raw)
	if err != nil {
		panic(err)
	}
	return doc
}

func TestParseAndExportFormats(t *testing.T) {
	doc := samplePlan()
	for _, format := range []string{"svg", "pdf", "dxf", "obj", "gltf"} {
		res, err := Export(doc, format)
		if err != nil {
			t.Fatalf("%s: %v", format, err)
		}
		if len(res.Data) == 0 {
			t.Fatalf("%s: empty output", format)
		}
		if res.Filename == "" || res.ContentType == "" {
			t.Fatalf("%s: missing metadata", format)
		}
	}
}

func TestExportSVGContainsRoom(t *testing.T) {
	res, err := Export(samplePlan(), "svg")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(res.Data), "Séjour") {
		t.Fatalf("svg missing room label: %s", res.Data[:min(200, len(res.Data))])
	}
}

func TestExportDXFIsQCADCompatible(t *testing.T) {
	doc := samplePlan()
	res, err := Export(doc, "dxf")
	if err != nil {
		t.Fatal(err)
	}
	s := string(res.Data)
	for _, want := range []string{"$ACADVER", "AC1009", "$INSUNITS", "LTYPE", "CONTINUOUS", "STYLE", "STANDARD", "WALLS", "ROOMS", "LABELS", "POLYLINE", "VERTEX", "SEQEND", "Sejour", "EOF"} {
		if !strings.Contains(s, want) {
			t.Fatalf("dxf missing %q (tool=%s)", want, res.Tool)
		}
	}
	if res.Tool != "qcad-dxf" && res.Tool != "qcad" {
		t.Fatalf("expected qcad tool tag, got %q", res.Tool)
	}
}

func TestDXFIsASCIIAndCRLF(t *testing.T) {
	raw := toQCADDXF(samplePlan())
	if !bytes.Contains(raw, []byte("\r\n")) {
		t.Fatal("DXF must use CRLF for Windows CAD")
	}
	for i, c := range raw {
		if c > 127 {
			t.Fatalf("non-ASCII byte at %d", i)
		}
	}
	if !looksLikeDXF(raw) {
		t.Fatal("writer output rejected by looksLikeDXF")
	}
}

func TestExportDXFIncludesOpenings(t *testing.T) {
	doc := samplePlan()
	doc.Openings = json.RawMessage(`[{"id":"o1","wall_id":"w1","type":"door","offset_m":1,"width_m":0.9}]`)
	s := string(toQCADDXF(doc))
	if !strings.Contains(s, "OPENINGS") {
		t.Fatal("opening layer missing")
	}
}

func TestNormalizeViaHTTP(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/normalize" || r.Method != http.MethodPost {
			t.Fatalf("bad request %s %s", r.Method, r.URL.Path)
		}
		w.Header().Set("Content-Type", "application/dxf")
		_, _ = w.Write([]byte("0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n"))
	}))
	defer srv.Close()
	out, ok := normalizeViaHTTP(srv.URL, []byte("0\nEOF\n"))
	if !ok || !strings.Contains(string(out), "EOF") {
		t.Fatalf("http normalize failed ok=%v", ok)
	}
}

func TestQCADBinaryEmptyWithoutEnv(t *testing.T) {
	t.Setenv("QCAD_BIN", "")
	// LookPath may still find a system install; normalize must not panic.
	_, _ = normalizeWithQCAD([]byte("0\nSECTION\n"))
}

func TestExportUnsupported(t *testing.T) {
	_, err := Export(samplePlan(), "dwg")
	if err == nil {
		t.Fatal("expected error for dwg")
	}
}

func TestParseInvalid(t *testing.T) {
	_, err := Parse(json.RawMessage(`{`))
	if err == nil {
		t.Fatal("expected parse error")
	}
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
