package export

import (
	"bytes"
	"fmt"
	"math"
	"strconv"
	"strings"
)

const (
	pdfPageW   = 842.0 // A4 landscape (pt)
	pdfPageH   = 595.0
	pdfMargin  = 36.0
	pdfHeaderH = 28.0
)

// toPlanPDF draws the floor plan as a real vector PDF (rooms, walls, labels).
// The previous stub wrote a technically tagged file whose content stream
// never painted anything a viewer could show — downloads opened on a blank
// page.
func toPlanPDF(doc *PlanDocument) []byte {
	if doc == nil {
		doc = &PlanDocument{}
	}
	stream := pdfContent(doc)

	var w pdfWriter
	w.buf.WriteString("%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
	_ = w.obj("<< /Type /Catalog /Pages 2 0 R >>")
	_ = w.obj("<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
	page := fmt.Sprintf(
		"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %s %s] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
		pdfNum(pdfPageW), pdfNum(pdfPageH),
	)
	_ = w.obj(page)
	_ = w.stream(stream)
	_ = w.obj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
	return w.finish()
}

func pdfContent(doc *PlanDocument) string {
	var b strings.Builder
	b.WriteString("0.96 0.96 0.95 rg 0 0 842 595 re f\n")
	b.WriteString("0.05 0.07 0.07 rg 36 555 770 24 re f\n")
	b.WriteString("BT /F1 11 Tf 1 1 1 rg 44 562 Td (Congo Architecture IA  -  plan 2D) Tj ET\n")

	xmin, ymin, xmax, ymax := extents(doc)
	bw := math.Max(xmax-xmin, 0.5)
	bh := math.Max(ymax-ymin, 0.5)
	availW := pdfPageW - 2*pdfMargin
	availH := pdfPageH - 2*pdfMargin - pdfHeaderH
	scale := math.Min(availW/bw, availH/bh) * 0.92
	offX := pdfMargin + (availW-bw*scale)/2
	offY := pdfMargin + (availH-bh*scale)/2

	px := func(x float64) float64 { return offX + (x-xmin)*scale }
	py := func(y float64) float64 { return offY + (y-ymin)*scale }

	meta := fmt.Sprintf(
		"%s m x %s m   |   %d piece(s)   |   %d mur(s)",
		pdfNum(bw), pdfNum(bh), len(doc.Rooms), len(doc.Walls),
	)
	fmt.Fprintf(&b, "BT /F1 9 Tf 0.35 0.35 0.35 rg 44 540 Td (%s) Tj ET\n", pdfEscape(meta))

	if len(doc.Rooms) == 0 && len(doc.Walls) == 0 {
		b.WriteString("BT /F1 14 Tf 0.45 0.45 0.45 rg 300 300 Td (Aucun plan a dessiner) Tj ET\n")
		return b.String()
	}

	fills := []string{
		"0.91 0.93 0.96",
		"0.93 0.90 0.84",
		"0.88 0.93 0.88",
		"0.93 0.88 0.90",
		"0.90 0.91 0.94",
	}
	b.WriteString("0.6 w 1 j 1 J\n")
	for i, room := range doc.Rooms {
		if len(room.Polygon) < 3 {
			continue
		}
		fmt.Fprintf(&b, "%s rg 0.42 0.49 0.58 RG\n", fills[i%len(fills)])
		for i, p := range room.Polygon {
			op := "l"
			if i == 0 {
				op = "m"
			}
			fmt.Fprintf(&b, "%s %s %s\n", pdfNum(px(p.X)), pdfNum(py(p.Y)), op)
		}
		b.WriteString("h B\n")
	}

	b.WriteString("0.12 0.16 0.22 RG 2.2 w\n")
	for _, wall := range doc.Walls {
		fmt.Fprintf(
			&b, "%s %s m %s %s l S\n",
			pdfNum(px(wall.A.X)), pdfNum(py(wall.A.Y)),
			pdfNum(px(wall.B.X)), pdfNum(py(wall.B.Y)),
		)
	}

	b.WriteString("0.96 0.96 0.95 RG 4 w\n")
	for _, opening := range doc.parsedOpenings() {
		wall := wallByID(doc, opening.WallID)
		if wall == nil {
			continue
		}
		a, c := openingSegment(*wall, opening.OffsetM, opening.WidthM)
		fmt.Fprintf(
			&b, "%s %s m %s %s l S\n",
			pdfNum(px(a.X)), pdfNum(py(a.Y)),
			pdfNum(px(c.X)), pdfNum(py(c.Y)),
		)
	}

	b.WriteString("0.14 0.16 0.18 rg\n")
	for _, room := range doc.Rooms {
		if len(room.Polygon) == 0 {
			continue
		}
		cx, cy := centroid(room.Polygon)
		label := room.Name
		if label == "" {
			label = room.Type
		}
		label = pdfEscape(label)
		if label == "" {
			continue
		}
		fmt.Fprintf(
			&b, "BT /F1 9 Tf %s %s Td (%s) Tj ET\n",
			pdfNum(px(cx)-float64(len(label))*2.2),
			pdfNum(py(cy)),
			label,
		)
	}
	return b.String()
}

func pdfNum(v float64) string {
	if math.IsNaN(v) || math.IsInf(v, 0) {
		return "0"
	}
	return strconv.FormatFloat(v, 'f', 2, 64)
}

func pdfEscape(s string) string {
	s = dxfASCII(s)
	return strings.NewReplacer(`\`, `\\`, `(`, `\(`, `)`, `\)`).Replace(s)
}

type pdfWriter struct {
	buf bytes.Buffer
	off []int
}

func (p *pdfWriter) obj(body string) int {
	p.off = append(p.off, p.buf.Len())
	n := len(p.off)
	fmt.Fprintf(&p.buf, "%d 0 obj\n%s\nendobj\n", n, body)
	return n
}

func (p *pdfWriter) stream(data string) int {
	p.off = append(p.off, p.buf.Len())
	n := len(p.off)
	fmt.Fprintf(&p.buf, "%d 0 obj\n<< /Length %d >>\nstream\n%s\nendstream\nendobj\n", n, len(data), data)
	return n
}

func (p *pdfWriter) finish() []byte {
	startxref := p.buf.Len()
	fmt.Fprintf(&p.buf, "xref\n0 %d\n0000000000 65535 f\r\n", len(p.off)+1)
	for _, off := range p.off {
		fmt.Fprintf(&p.buf, "%010d 00000 n\r\n", off)
	}
	fmt.Fprintf(
		&p.buf,
		"trailer<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n",
		len(p.off)+1, startxref,
	)
	return p.buf.Bytes()
}
