package export

import (
	"bytes"
	"encoding/json"
	"fmt"
	"math"
	"strings"
	"unicode"
)

func (d *PlanDocument) parsedOpenings() []Opening {
	if len(d.Openings) == 0 {
		return nil
	}
	var out []Opening
	if err := json.Unmarshal(d.Openings, &out); err != nil {
		return nil
	}
	return out
}

func wallByID(doc *PlanDocument, id string) *Wall {
	for i := range doc.Walls {
		if doc.Walls[i].ID == id {
			return &doc.Walls[i]
		}
	}
	return nil
}

func openingSegment(w Wall, offset, width float64) (Point, Point) {
	dx := w.B.X - w.A.X
	dy := w.B.Y - w.A.Y
	length := math.Hypot(dx, dy)
	if length < 1e-9 {
		return w.A, w.B
	}
	ux, uy := dx/length, dy/length
	if offset < 0 {
		offset = 0
	}
	if width < 0.4 {
		width = 0.9
	}
	if offset+width > length {
		offset = math.Max(0, length-width)
	}
	a := Point{X: w.A.X + ux*offset, Y: w.A.Y + uy*offset}
	b := Point{X: a.X + ux*width, Y: a.Y + uy*width}
	return a, b
}

// toQCADDXF writes DXF R12 (AC1009). QCAD, LibreCAD, AutoCAD, DraftSight open this
// reliably. Incomplete AC1015 files are often rejected.
func toQCADDXF(doc *PlanDocument) []byte {
	var b dxfBuf
	xmin, ymin, xmax, ymax := extents(doc)

	b.pair(0, "SECTION")
	b.pair(2, "HEADER")
	b.pair(9, "$ACADVER")
	b.pair(1, "AC1009")
	b.pair(9, "$INSUNITS")
	b.pair(70, "6")
	b.pair(9, "$MEASUREMENT")
	b.pair(70, "1")
	b.pair(9, "$EXTMIN")
	b.pair(10, fmt.Sprintf("%.6f", xmin))
	b.pair(20, fmt.Sprintf("%.6f", ymin))
	b.pair(30, "0.0")
	b.pair(9, "$EXTMAX")
	b.pair(10, fmt.Sprintf("%.6f", xmax))
	b.pair(20, fmt.Sprintf("%.6f", ymax))
	b.pair(30, "0.0")
	b.pair(0, "ENDSEC")

	b.pair(0, "SECTION")
	b.pair(2, "TABLES")

	b.pair(0, "TABLE")
	b.pair(2, "LTYPE")
	b.pair(70, "1")
	b.pair(0, "LTYPE")
	b.pair(2, "CONTINUOUS")
	b.pair(70, "0")
	b.pair(3, "Solid line")
	b.pair(72, "65")
	b.pair(73, "0")
	b.pair(40, "0.0")
	b.pair(0, "ENDTAB")

	b.pair(0, "TABLE")
	b.pair(2, "LAYER")
	b.pair(70, "4")
	writeLayer(&b, "WALLS", 7)
	writeLayer(&b, "ROOMS", 8)
	writeLayer(&b, "OPENINGS", 4)
	writeLayer(&b, "LABELS", 2)
	b.pair(0, "ENDTAB")

	b.pair(0, "TABLE")
	b.pair(2, "STYLE")
	b.pair(70, "1")
	b.pair(0, "STYLE")
	b.pair(2, "STANDARD")
	b.pair(70, "0")
	b.pair(40, "0.0")
	b.pair(41, "1.0")
	b.pair(50, "0.0")
	b.pair(71, "0")
	b.pair(42, "1.0")
	b.pair(3, "txt")
	b.pair(4, "")
	b.pair(0, "ENDTAB")

	b.pair(0, "ENDSEC")

	b.pair(0, "SECTION")
	b.pair(2, "ENTITIES")
	for _, wall := range doc.Walls {
		writeLine(&b, "WALLS", wall.A, wall.B)
	}
	for _, room := range doc.Rooms {
		if len(room.Polygon) >= 3 {
			writePolyline(&b, "ROOMS", room.Polygon, true)
		}
		label := strings.TrimSpace(room.Name)
		if label == "" {
			label = room.Type
		}
		if label != "" && len(room.Polygon) > 0 {
			cx, cy := centroid(room.Polygon)
			writeText(&b, "LABELS", cx, cy, 0.35, label)
		}
	}
	for _, op := range doc.parsedOpenings() {
		w := wallByID(doc, op.WallID)
		if w == nil {
			continue
		}
		a, p := openingSegment(*w, op.OffsetM, op.WidthM)
		writeLine(&b, "OPENINGS", a, p)
	}
	b.pair(0, "ENDSEC")
	b.pair(0, "EOF")
	return b.Bytes()
}

type dxfBuf struct{ bytes.Buffer }

func (b *dxfBuf) pair(code int, value string) {
	fmt.Fprintf(&b.Buffer, "%d\r\n%s\r\n", code, value)
}

func writeLayer(buf *dxfBuf, name string, color int) {
	buf.pair(0, "LAYER")
	buf.pair(2, name)
	buf.pair(70, "0")
	buf.pair(62, fmt.Sprintf("%d", color))
	buf.pair(6, "CONTINUOUS")
}

func writeLine(buf *dxfBuf, layer string, a, b Point) {
	buf.pair(0, "LINE")
	buf.pair(8, layer)
	buf.pair(10, fmt.Sprintf("%.6f", a.X))
	buf.pair(20, fmt.Sprintf("%.6f", a.Y))
	buf.pair(30, "0.0")
	buf.pair(11, fmt.Sprintf("%.6f", b.X))
	buf.pair(21, fmt.Sprintf("%.6f", b.Y))
	buf.pair(31, "0.0")
}

func writePolyline(buf *dxfBuf, layer string, pts []Point, closed bool) {
	flags := 0
	if closed {
		flags = 1
	}
	buf.pair(0, "POLYLINE")
	buf.pair(8, layer)
	buf.pair(66, "1")
	buf.pair(70, fmt.Sprintf("%d", flags))
	for _, p := range pts {
		buf.pair(0, "VERTEX")
		buf.pair(8, layer)
		buf.pair(10, fmt.Sprintf("%.6f", p.X))
		buf.pair(20, fmt.Sprintf("%.6f", p.Y))
		buf.pair(30, "0.0")
	}
	buf.pair(0, "SEQEND")
	buf.pair(8, layer)
}

func writeText(buf *dxfBuf, layer string, x, y, height float64, text string) {
	buf.pair(0, "TEXT")
	buf.pair(8, layer)
	buf.pair(10, fmt.Sprintf("%.6f", x))
	buf.pair(20, fmt.Sprintf("%.6f", y))
	buf.pair(30, "0.0")
	buf.pair(40, fmt.Sprintf("%.6f", height))
	buf.pair(1, dxfASCII(text))
	buf.pair(7, "STANDARD")
}

func extents(doc *PlanDocument) (xmin, ymin, xmax, ymax float64) {
	xmax = doc.Floor.Bounds.Width
	ymax = doc.Floor.Bounds.Depth
	if xmax <= 0 {
		xmax = 1
	}
	if ymax <= 0 {
		ymax = 1
	}
	touch := func(x, y float64) {
		xmin = math.Min(xmin, x)
		ymin = math.Min(ymin, y)
		xmax = math.Max(xmax, x)
		ymax = math.Max(ymax, y)
	}
	for _, w := range doc.Walls {
		touch(w.A.X, w.A.Y)
		touch(w.B.X, w.B.Y)
	}
	for _, r := range doc.Rooms {
		for _, p := range r.Polygon {
			touch(p.X, p.Y)
		}
	}
	return xmin, ymin, xmax, ymax
}

func dxfASCII(s string) string {
	s = strings.NewReplacer("\n", " ", "\r", "", "\\", "/", "{", "(", "}", ")").Replace(s)
	repl := strings.NewReplacer(
		"à", "a", "â", "a", "ä", "a", "á", "a",
		"é", "e", "è", "e", "ê", "e", "ë", "e",
		"î", "i", "ï", "i", "í", "i",
		"ô", "o", "ö", "o", "ó", "o",
		"ù", "u", "û", "u", "ü", "u", "ú", "u",
		"ç", "c", "œ", "oe", "æ", "ae",
		"À", "A", "Â", "A", "É", "E", "È", "E", "Ç", "C",
		"’", "'", "‘", "'", "–", "-", "—", "-",
	)
	s = repl.Replace(s)
	var b strings.Builder
	for _, r := range s {
		if r <= unicode.MaxASCII && unicode.IsPrint(r) {
			b.WriteRune(r)
		}
	}
	out := strings.TrimSpace(b.String())
	if out == "" {
		return "piece"
	}
	return out
}

func looksLikeDXF(raw []byte) bool {
	if len(raw) < 16 {
		return false
	}
	n := 64
	if len(raw) < n {
		n = len(raw)
	}
	head := strings.ToLower(string(raw[:n]))
	if strings.Contains(head, "<html") || strings.Contains(head, "{") {
		return false
	}
	return bytes.Contains(raw, []byte("EOF")) && (bytes.Contains(raw, []byte("SECTION")) || bytes.Contains(raw, []byte("ENTITIES")))
}

func exportDXF(doc *PlanDocument) ([]byte, string) {
	raw := toQCADDXF(doc)
	normalized, ok := normalizeWithQCAD(raw)
	if ok && looksLikeDXF(normalized) {
		return normalized, "qcad"
	}
	return raw, "qcad-dxf"
}
