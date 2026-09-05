package plan

import (
	"encoding/json"
	"fmt"
	"math"
	"strings"
)

const (
	complianceTol        = 0.15
	complianceSeam       = 0.55
	complianceDisclaimer = "Indicatif (heuristiques d’habitabilité). Pas un contrôle réglementaire ni un permis."
)

var habitableTypes = map[string]struct{}{
	"living": {}, "bedroom": {}, "dining": {}, "office": {},
}

type Check struct {
	Key    string `json:"key"`
	Label  string `json:"label"`
	OK     bool   `json:"ok"`
	Weight int    `json:"weight"`
	Detail string `json:"detail,omitempty"`
}

type Report struct {
	Score      int     `json:"score"`
	Grade      string  `json:"grade"`
	Passed     int     `json:"passed"`
	Total      int     `json:"total"`
	Checks     []Check `json:"checks"`
	Disclaimer string  `json:"disclaimer"`
}

type evalPlan struct {
	Floor struct {
		HeightM float64 `json:"height_m"`
		Bounds  struct {
			Width float64 `json:"width"`
			Depth float64 `json:"depth"`
		} `json:"bounds"`
	} `json:"floor"`
	Walls    []evalWall    `json:"walls"`
	Rooms    []evalRoom    `json:"rooms"`
	Openings []evalOpening `json:"openings"`
}

type evalWall struct {
	ID string `json:"id"`
	A  Point  `json:"a"`
	B  Point  `json:"b"`
}

type evalRoom struct {
	ID      string  `json:"id"`
	Name    string  `json:"name"`
	Type    string  `json:"type"`
	Polygon []Point `json:"polygon"`
}

type evalOpening struct {
	ID     string  `json:"id"`
	WallID string  `json:"wall_id"`
	Type   string  `json:"type"`
	WidthM float64 `json:"width_m"`
}

func EvaluateRaw(raw json.RawMessage) json.RawMessage {
	b, err := json.Marshal(Evaluate(raw))
	if err != nil {
		return json.RawMessage(`{"score":0,"grade":"E","passed":0,"total":0,"checks":[],"disclaimer":"` + complianceDisclaimer + `"}`)
	}
	return b
}

func Evaluate(raw json.RawMessage) Report {
	var doc evalPlan
	if len(raw) > 0 {
		_ = json.Unmarshal(raw, &doc)
	}
	validRooms := make([]evalRoom, 0, len(doc.Rooms))
	for _, r := range doc.Rooms {
		if len(r.Polygon) >= 3 {
			validRooms = append(validRooms, r)
		}
	}
	width, depth, height := doc.Floor.Bounds.Width, doc.Floor.Bounds.Depth, doc.Floor.HeightM
	byID := map[string]evalWall{}
	for _, w := range doc.Walls {
		byID[w.ID] = w
	}

	var living, beds, kitchens, baths, halls, habit []evalRoom
	for _, r := range validRooms {
		switch r.Type {
		case "living":
			living = append(living, r)
		case "bedroom":
			beds = append(beds, r)
		case "kitchen":
			kitchens = append(kitchens, r)
		case "bathroom":
			baths = append(baths, r)
		case "hallway":
			halls = append(halls, r)
		}
		if _, ok := habitableTypes[r.Type]; ok {
			habit = append(habit, r)
		}
	}

	checks := make([]Check, 0, 15)
	add := func(key, label string, ok bool, weight int, detail string) {
		checks = append(checks, Check{Key: key, Label: label, OK: ok, Weight: weight, Detail: detail})
	}

	add("height", "Hauteur sous plafond ≥ 2,20 m", height >= 2.20, 8, fmt.Sprintf("%.2f m", height))
	add("living", "Séjour présent", len(living) > 0, 8, "")
	livArea := 0.0
	if len(living) > 0 {
		livArea = polyArea(living[0].Polygon)
	}
	add("living_area", "Séjour ≥ 9 m²", livArea >= 9, 10, fmt.Sprintf("%.1f m²", livArea))
	smallBeds := 0
	for _, r := range beds {
		if polyArea(r.Polygon) < 9 {
			smallBeds++
		}
	}
	bedDetail := "aucune chambre"
	if len(beds) > 0 && smallBeds == 0 {
		bedDetail = "ok"
	} else if smallBeds > 0 {
		bedDetail = fmt.Sprintf("%d trop petite(s)", smallBeds)
	}
	add("bedrooms", "Chaque chambre ≥ 9 m²", len(beds) > 0 && smallBeds == 0, 10, bedDetail)
	add("kitchen", "Cuisine présente", len(kitchens) > 0, 6, "")
	add("bathroom", "Salle de bain présente", len(baths) > 0, 6, "")

	env := envelope(validRooms)
	var noFacade []string
	for _, r := range habit {
		if !touchesOuter(r.Polygon, width, depth, env) {
			noFacade = append(noFacade, roomLabel(r.Name, r.Type))
		}
	}
	facadeDetail := "ok"
	if len(noFacade) > 0 {
		facadeDetail = strings.Join(noFacade, ", ")
	}
	add("facade", "Pièces habitables sur façade", len(habit) > 0 && len(noFacade) == 0, 12, facadeDetail)

	hasWindow := false
	for _, o := range doc.Openings {
		if o.Type == "window" {
			hasWindow = true
			break
		}
	}
	add("window", "Au moins une fenêtre", hasWindow, 6, "")

	hasEntry := false
	for _, o := range doc.Openings {
		if o.Type != "door" {
			continue
		}
		w, ok := byID[o.WallID]
		if ok && isOuterWall(w.ID, w.A, w.B, width, depth) {
			hasEntry = true
			break
		}
	}
	add("entry", "Porte d’entrée sur façade", hasEntry, 6, "")

	isolated := isolatedRooms(validRooms)
	accDetail := "ok"
	if len(isolated) > 0 {
		accDetail = strings.Join(isolated, ", ")
	}
	add("access", "Pièces accessibles (bord partagé)", len(isolated) == 0, 10, accDetail)

	narrowHall := false
	for _, r := range halls {
		w, d := sides(r.Polygon)
		if math.Min(w, d) < 0.90 {
			narrowHall = true
		}
	}
	hallDetail := "pas de couloir"
	if len(halls) > 0 {
		if narrowHall {
			hallDetail = "trop étroit"
		} else {
			hallDetail = "ok"
		}
	}
	add("hall", "Couloir ≥ 0,90 m si présent", !narrowHall, 6, hallDetail)

	thinDoors := false
	for _, o := range doc.Openings {
		if o.Type == "door" && o.WidthM < 0.80 {
			thinDoors = true
		}
	}
	add("doors", "Portes ≥ 0,80 m", len(doc.Openings) > 0 && !thinDoors, 4, "")

	ortho := len(doc.Walls) > 0
	for _, w := range doc.Walls {
		if math.Abs(w.A.X-w.B.X) > 1e-6 && math.Abs(w.A.Y-w.B.Y) > 1e-6 {
			ortho = false
			break
		}
	}
	add("ortho", "Murs orthogonaux", ortho, 6, "")

	overlaps := 0.0
	for i, a := range validRooms {
		for _, b := range validRooms[i+1:] {
			overlaps += overlapArea(a.Polygon, b.Polygon)
		}
	}
	add("overlap", "Pas de chevauchement", overlaps < 0.25, 8, fmt.Sprintf("%.2f m²", overlaps))

	oob := false
	if width > 0 && depth > 0 {
		for _, r := range validRooms {
			x0, y0, x1, y1 := bbox(r.Polygon)
			if x0 < -complianceTol || y0 < -complianceTol || x1 > width+complianceTol || y1 > depth+complianceTol {
				oob = true
			}
		}
	}
	add("bounds", "Pièces dans l’emprise", len(validRooms) > 0 && !oob, 4, "")

	totalW, got, passed := 0, 0, 0
	for _, c := range checks {
		totalW += c.Weight
		if c.OK {
			got += c.Weight
			passed++
		}
	}
	score := 0
	if totalW > 0 {
		score = int(math.Round(100 * float64(got) / float64(totalW)))
	}
	grade := "E"
	switch {
	case score >= 80:
		grade = "A"
	case score >= 65:
		grade = "B"
	case score >= 50:
		grade = "C"
	case score >= 35:
		grade = "D"
	}
	return Report{
		Score: score, Grade: grade, Passed: passed, Total: len(checks),
		Checks: checks, Disclaimer: complianceDisclaimer,
	}
}

func roomLabel(name, typ string) string {
	if name != "" {
		return name
	}
	return typ
}

func polyArea(poly []Point) float64 {
	if len(poly) < 3 {
		return 0
	}
	acc := 0.0
	for i, p := range poly {
		q := poly[(i+1)%len(poly)]
		acc += p.X*q.Y - q.X*p.Y
	}
	return math.Abs(acc) / 2
}

func bbox(poly []Point) (float64, float64, float64, float64) {
	x0, y0, x1, y1 := poly[0].X, poly[0].Y, poly[0].X, poly[0].Y
	for _, p := range poly[1:] {
		x0 = math.Min(x0, p.X)
		y0 = math.Min(y0, p.Y)
		x1 = math.Max(x1, p.X)
		y1 = math.Max(y1, p.Y)
	}
	return x0, y0, x1, y1
}

func sides(poly []Point) (float64, float64) {
	x0, y0, x1, y1 := bbox(poly)
	return x1 - x0, y1 - y0
}

func overlapArea(a, b []Point) float64 {
	ax0, ay0, ax1, ay1 := bbox(a)
	bx0, by0, bx1, by1 := bbox(b)
	ix := math.Max(0, math.Min(ax1, bx1)-math.Max(ax0, bx0))
	iy := math.Max(0, math.Min(ay1, by1)-math.Max(ay0, by0))
	return ix * iy
}

func shareEdge(a, b []Point) bool {
	ax0, ay0, ax1, ay1 := bbox(a)
	bx0, by0, bx1, by1 := bbox(b)
	yOv := math.Min(ay1, by1) - math.Max(ay0, by0)
	xOv := math.Min(ax1, bx1) - math.Max(ax0, bx0)
	xTouch := math.Abs(ax1-bx0) <= complianceTol || math.Abs(bx1-ax0) <= complianceTol
	yTouch := math.Abs(ay1-by0) <= complianceTol || math.Abs(by1-ay0) <= complianceTol
	return (xTouch && yOv >= complianceSeam) || (yTouch && xOv >= complianceSeam)
}

func isolatedRooms(rooms []evalRoom) []string {
	if len(rooms) == 0 {
		return nil
	}
	var hubs []int
	for i, r := range rooms {
		if r.Type == "living" || r.Type == "hallway" {
			hubs = append(hubs, i)
		}
	}
	if len(hubs) == 0 {
		for i := range rooms {
			hubs = append(hubs, i)
		}
	}
	seen := map[int]bool{}
	stack := append([]int{}, hubs...)
	for _, i := range hubs {
		seen[i] = true
	}
	for len(stack) > 0 {
		i := stack[len(stack)-1]
		stack = stack[:len(stack)-1]
		for j, other := range rooms {
			if seen[j] {
				continue
			}
			if shareEdge(rooms[i].Polygon, other.Polygon) {
				seen[j] = true
				stack = append(stack, j)
			}
		}
	}
	var isolated []string
	for i, r := range rooms {
		if !seen[i] {
			isolated = append(isolated, roomLabel(r.Name, r.Type))
		}
	}
	return isolated
}

func envelope(rooms []evalRoom) *[4]float64 {
	if len(rooms) == 0 {
		return nil
	}
	x0, y0, x1, y1 := bbox(rooms[0].Polygon)
	for _, r := range rooms[1:] {
		a, b, c, d := bbox(r.Polygon)
		x0, y0 = math.Min(x0, a), math.Min(y0, b)
		x1, y1 = math.Max(x1, c), math.Max(y1, d)
	}
	return &[4]float64{x0, y0, x1, y1}
}

func touchesOuter(poly []Point, width, depth float64, env *[4]float64) bool {
	x0, y0, x1, y1 := bbox(poly)
	if env != nil {
		if x0 <= env[0]+complianceTol || y0 <= env[1]+complianceTol || x1 >= env[2]-complianceTol || y1 >= env[3]-complianceTol {
			return true
		}
	}
	return x0 <= complianceTol || y0 <= complianceTol || (width > 0 && x1 >= width-complianceTol) || (depth > 0 && y1 >= depth-complianceTol)
}

func isOuterWall(id string, a, b Point, width, depth float64) bool {
	xs := []float64{a.X, b.X}
	ys := []float64{a.Y, b.Y}
	maxX, minX := math.Max(xs[0], xs[1]), math.Min(xs[0], xs[1])
	maxY, minY := math.Max(ys[0], ys[1]), math.Min(ys[0], ys[1])
	return maxX <= complianceTol || minX >= width-complianceTol ||
		maxY <= complianceTol || minY >= depth-complianceTol ||
		strings.HasPrefix(id, "w_outer")
}
