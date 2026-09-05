package export

import (
	"bytes"
	"encoding/json"
	"fmt"
	"strings"
)

type Point struct {
	X float64 `json:"x"`
	Y float64 `json:"y"`
}

type Wall struct {
	ID         string  `json:"id"`
	A          Point   `json:"a"`
	B          Point   `json:"b"`
	ThicknessM float64 `json:"thickness_m"`
}

type Room struct {
	ID      string  `json:"id"`
	Name    string  `json:"name"`
	Type    string  `json:"type"`
	Polygon []Point `json:"polygon"`
}

type PlanDocument struct {
	Version string `json:"version"`
	Units   string `json:"units"`
	Floor   struct {
		Level   int     `json:"level"`
		HeightM float64 `json:"height_m"`
		Bounds  struct {
			Width float64 `json:"width"`
			Depth float64 `json:"depth"`
		} `json:"bounds"`
	} `json:"floor"`
	Walls    []Wall          `json:"walls"`
	Rooms    []Room          `json:"rooms"`
	Openings json.RawMessage `json:"openings"`
}

type Opening struct {
	ID      string  `json:"id"`
	WallID  string  `json:"wall_id"`
	Type    string  `json:"type"`
	OffsetM float64 `json:"offset_m"`
	WidthM  float64 `json:"width_m"`
}

type Result struct {
	ContentType string
	Filename    string
	Data        []byte
	Tool        string // "qcad-dxf" writer, or "qcad" after CLI normalize
}

func Parse(raw json.RawMessage) (*PlanDocument, error) {
	var doc PlanDocument
	if err := json.Unmarshal(raw, &doc); err != nil {
		return nil, err
	}
	return &doc, nil
}

func Export(doc *PlanDocument, format string) (*Result, error) {
	switch strings.ToLower(format) {
	case "svg":
		b := toSVG(doc)
		return &Result{ContentType: "image/svg+xml", Filename: "plan.svg", Data: b}, nil
	case "pdf":
		// Minimal PDF wrapping the SVG text representation for MVP.
		b := toSimplePDF(doc)
		return &Result{ContentType: "application/pdf", Filename: "plan.pdf", Data: b}, nil
	case "dxf":
		b, tool := exportDXF(doc)
		return &Result{ContentType: "application/x-dxf", Filename: "plan.dxf", Data: b, Tool: tool}, nil
	case "obj":
		b := toOBJ(doc)
		return &Result{ContentType: "model/obj", Filename: "plan.obj", Data: b}, nil
	case "gltf", "glb":
		b := toGLTF(doc)
		return &Result{ContentType: "model/gltf+json", Filename: "plan.gltf", Data: b}, nil
	default:
		return nil, fmt.Errorf("unsupported format: %s", format)
	}
}

func toSVG(doc *PlanDocument) []byte {
	var buf bytes.Buffer
	w := doc.Floor.Bounds.Width
	d := doc.Floor.Bounds.Depth
	scale := 40.0
	buf.WriteString(fmt.Sprintf(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %g %g">`, w*scale+40, d*scale+40))
	buf.WriteString(`<rect width="100%" height="100%" fill="#f7f4ef"/>`)
	for _, r := range doc.Rooms {
		buf.WriteString(`<polygon points="`)
		for i, p := range r.Polygon {
			if i > 0 {
				buf.WriteByte(' ')
			}
			buf.WriteString(fmt.Sprintf("%g,%g", 20+p.X*scale, 20+p.Y*scale))
		}
		buf.WriteString(`" fill="#e8eef5" stroke="#6b7c93" stroke-width="1"/>`)
		if len(r.Polygon) > 0 {
			cx, cy := centroid(r.Polygon)
			label := r.Name
			if label == "" {
				label = r.Type
			}
			buf.WriteString(fmt.Sprintf(`<text x="%g" y="%g" font-size="12" fill="#243447">%s</text>`, 20+cx*scale, 20+cy*scale, xmlEscape(label)))
		}
	}
	for _, wall := range doc.Walls {
		buf.WriteString(fmt.Sprintf(
			`<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="#1f2a37" stroke-width="%g"/>`,
			20+wall.A.X*scale, 20+wall.A.Y*scale, 20+wall.B.X*scale, 20+wall.B.Y*scale, max(2, wall.ThicknessM*scale),
		))
	}
	buf.WriteString(`</svg>`)
	return buf.Bytes()
}

func toOBJ(doc *PlanDocument) []byte {
	var buf bytes.Buffer
	buf.WriteString("# A-AI plan extrusion stub\n")
	h := doc.Floor.HeightM
	vid := 1
	for _, wall := range doc.Walls {
		// simple vertical quad
		buf.WriteString(fmt.Sprintf("v %g %g %g\n", wall.A.X, 0.0, wall.A.Y))
		buf.WriteString(fmt.Sprintf("v %g %g %g\n", wall.B.X, 0.0, wall.B.Y))
		buf.WriteString(fmt.Sprintf("v %g %g %g\n", wall.B.X, h, wall.B.Y))
		buf.WriteString(fmt.Sprintf("v %g %g %g\n", wall.A.X, h, wall.A.Y))
		buf.WriteString(fmt.Sprintf("f %d %d %d %d\n", vid, vid+1, vid+2, vid+3))
		vid += 4
	}
	return buf.Bytes()
}

func toGLTF(doc *PlanDocument) []byte {
	// Minimal glTF JSON without binary buffer — positions as accessors would be needed for real viewers.
	// For MVP we embed a note and bbox; blender worker produces real glTF.
	payload := map[string]any{
		"asset":  map[string]any{"version": "2.0", "generator": "a-ai-export-stub"},
		"scenes": []any{map[string]any{"nodes": []int{0}}},
		"nodes":  []any{map[string]any{"name": "PlanStub", "mesh": 0}},
		"meshes": []any{map[string]any{"name": "Walls", "primitives": []any{}}},
		"extras": map[string]any{
			"bounds": doc.Floor.Bounds,
			"walls":  len(doc.Walls),
			"rooms":  len(doc.Rooms),
		},
	}
	b, _ := json.MarshalIndent(payload, "", "  ")
	return b
}

func toSimplePDF(doc *PlanDocument) []byte {
	// Extremely small PDF with text summary (valid enough for download MVP).
	content := fmt.Sprintf("A-AI Plan\\nWalls: %d\\nRooms: %d\\nSize: %.1fx%.1fm",
		len(doc.Walls), len(doc.Rooms), doc.Floor.Bounds.Width, doc.Floor.Bounds.Depth)
	var buf bytes.Buffer
	buf.WriteString("%PDF-1.1\n")
	o1 := buf.Len()
	buf.WriteString("1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
	o2 := buf.Len()
	buf.WriteString("2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
	o3 := buf.Len()
	buf.WriteString("3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n")
	stream := fmt.Sprintf("BT /F1 18 Tf 50 700 Td (%s) Tj ET", content)
	o4 := buf.Len()
	buf.WriteString(fmt.Sprintf("4 0 obj<< /Length %d >>stream\n%s\nendstream\nendobj\n", len(stream), stream))
	o5 := buf.Len()
	buf.WriteString("5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")
	xref := buf.Len()
	buf.WriteString("xref\n0 6\n0000000000 65535 f \n")
	for _, off := range []int{o1, o2, o3, o4, o5} {
		buf.WriteString(fmt.Sprintf("%010d 00000 n \n", off))
	}
	buf.WriteString(fmt.Sprintf("trailer<< /Size 6 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF", xref))
	return buf.Bytes()
}

func centroid(pts []Point) (float64, float64) {
	var x, y float64
	for _, p := range pts {
		x += p.X
		y += p.Y
	}
	n := float64(len(pts))
	return x / n, y / n
}

func xmlEscape(s string) string {
	r := strings.NewReplacer("&", "&amp;", "<", "&lt;", ">", "&gt;", "\"", "&quot;")
	return r.Replace(s)
}

func max(a, b float64) float64 {
	if a > b {
		return a
	}
	return b
}
