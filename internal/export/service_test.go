package export

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strconv"
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

func TestEditedRevisionGeometryMatchesSVGAndDXFExports(t *testing.T) {
	doc := samplePlan()
	doc.Rooms[0].Name = "Cuisine éditée"
	doc.Rooms[0].Polygon = []Point{
		{X: 1.25, Y: 0.5},
		{X: 6.25, Y: 0.5},
		{X: 6.25, Y: 4.5},
		{X: 1.25, Y: 4.5},
	}

	svg, err := Export(doc, "svg")
	if err != nil {
		t.Fatal(err)
	}
	dxf, err := Export(doc, "dxf")
	if err != nil {
		t.Fatal(err)
	}

	// SVG uses a 40 px/m scale and 20 px origin offset; DXF retains metres.
	wantSVGPolygon := `points="70,40 270,40 270,200 70,200"`
	if !strings.Contains(string(svg.Data), wantSVGPolygon) {
		t.Errorf("SVG polygon vertices do not match edited document: %s", svg.Data)
	}
	wantDXFVertices := []Point{
		{X: 1.25, Y: 0.5},
		{X: 6.25, Y: 0.5},
		{X: 6.25, Y: 4.5},
		{X: 1.25, Y: 4.5},
	}
	if got := dxfVertices(dxf.Data); !reflect.DeepEqual(got, wantDXFVertices) {
		t.Errorf("DXF room vertices = %#v, want %#v", got, wantDXFVertices)
	}
	if !strings.Contains(string(svg.Data), "Cuisine éditée") {
		t.Error("SVG is missing the edited room label")
	}
	if !strings.Contains(string(dxf.Data), "Cuisine editee") {
		t.Error("DXF is missing the same edited room label")
	}
}

func dxfVertices(raw []byte) []Point {
	lines := strings.Split(string(raw), "\r\n")
	vertices := make([]Point, 0, 4)
	var current *Point
	currentLayer := ""
	for i := 0; i+1 < len(lines); i += 2 {
		code, value := lines[i], lines[i+1]
		if code == "0" {
			if current != nil && currentLayer == "ROOMS" {
				vertices = append(vertices, *current)
			}
			current = nil
			currentLayer = ""
			if value == "VERTEX" {
				current = &Point{}
			}
		}
		if current == nil {
			continue
		}
		if code == "8" {
			currentLayer = value
			continue
		}
		coordinate, err := strconv.ParseFloat(value, 64)
		if err != nil {
			continue
		}
		switch code {
		case "10":
			current.X = coordinate
		case "20":
			current.Y = coordinate
		}
	}
	if current != nil && currentLayer == "ROOMS" {
		vertices = append(vertices, *current)
	}
	return vertices
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

func TestExportPDFDrawsThePlan(t *testing.T) {
	res, err := Export(samplePlan(), "pdf")
	if err != nil {
		t.Fatal(err)
	}
	raw := res.Data
	if !bytes.HasPrefix(raw, []byte("%PDF-")) {
		t.Fatal("missing PDF header")
	}
	if !bytes.Contains(raw, []byte("%%EOF")) {
		t.Fatal("missing PDF trailer")
	}
	body := string(raw)
	if !strings.Contains(body, "Sejour") {
		t.Fatalf("pdf missing room label: %s", body[:min(400, len(body))])
	}
	if !strings.Contains(body, "Congo Architecture IA") {
		t.Fatal("pdf missing branded title")
	}
	if !strings.Contains(body, " re f") {
		t.Fatal("pdf has no filled path (blank page)")
	}
	if len(raw) < 800 {
		t.Fatalf("pdf too small to contain a plan (%d bytes)", len(raw))
	}
}

func TestPDFXrefEntriesAre20Bytes(t *testing.T) {
	raw := toPlanPDF(samplePlan())
	startMarker := []byte("startxref\n")
	startAt := bytes.LastIndex(raw, startMarker)
	if startAt < 0 {
		t.Fatal("missing startxref")
	}
	startLine := raw[startAt+len(startMarker):]
	startEnd := bytes.IndexByte(startLine, '\n')
	if startEnd < 0 {
		t.Fatal("unterminated startxref offset")
	}
	xrefOffset, err := strconv.Atoi(string(startLine[:startEnd]))
	if err != nil || xrefOffset < 0 || xrefOffset >= len(raw) {
		t.Fatalf("invalid startxref offset %q: %v", startLine[:startEnd], err)
	}
	if !bytes.HasPrefix(raw[xrefOffset:], []byte("xref\n")) {
		t.Fatalf("startxref points to %q, want xref table", raw[xrefOffset:min(xrefOffset+8, len(raw))])
	}

	section := raw[xrefOffset+len("xref\n"):]
	sectionEnd := bytes.IndexByte(section, '\n')
	if sectionEnd < 0 {
		t.Fatal("missing xref subsection header")
	}
	header := strings.Fields(string(section[:sectionEnd]))
	if len(header) != 2 || header[0] != "0" {
		t.Fatalf("invalid xref subsection header %q", section[:sectionEnd])
	}
	entryCount, err := strconv.Atoi(header[1])
	if err != nil || entryCount < 2 {
		t.Fatalf("invalid xref entry count %q: %v", header[1], err)
	}
	entryStart := xrefOffset + len("xref\n") + sectionEnd + 1
	for objectID := 0; objectID < entryCount; objectID++ {
		rowEnd := entryStart + 20
		if rowEnd > len(raw) {
			t.Fatalf("truncated xref at object %d", objectID)
		}
		row := raw[entryStart:rowEnd]
		if row[18] != '\r' || row[19] != '\n' {
			t.Fatalf("xref row %d is not 20 bytes ending in CRLF: %q", objectID, row)
		}
		fields := strings.Fields(string(row))
		if len(fields) != 3 {
			t.Fatalf("malformed xref row %d: %q", objectID, row)
		}
		if objectID == 0 {
			if fields[1] != "65535" || fields[2] != "f" {
				t.Fatalf("object zero xref entry is invalid: %q", row)
			}
		} else {
			objectOffset, err := strconv.Atoi(fields[0])
			if err != nil || objectOffset < 0 || objectOffset >= len(raw) {
				t.Fatalf("invalid offset for object %d: %q", objectID, fields[0])
			}
			objectHeader := []byte(strconv.Itoa(objectID) + " 0 obj\n")
			if !bytes.HasPrefix(raw[objectOffset:], objectHeader) {
				t.Fatalf("xref object %d offset does not point to its header", objectID)
			}
		}
		entryStart = rowEnd
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
