package plan

import (
	"encoding/json"
	"fmt"
	"math"
)

type Point struct {
	X float64 `json:"x"`
	Y float64 `json:"y"`
}

type Document struct {
	Version string `json:"version"`
	Units   string `json:"units"`
	Floor   struct {
		Bounds struct {
			Width float64 `json:"width"`
			Depth float64 `json:"depth"`
		} `json:"bounds"`
	} `json:"floor"`
	Walls []struct {
		ID string `json:"id"`
		A  Point  `json:"a"`
		B  Point  `json:"b"`
	} `json:"walls"`
	Rooms []struct {
		ID      string  `json:"id"`
		Polygon []Point `json:"polygon"`
	} `json:"rooms"`
	Openings []struct {
		ID     string  `json:"id"`
		WallID string  `json:"wall_id"`
		Type   string  `json:"type"`
		WidthM float64 `json:"width_m"`
	} `json:"openings"`
}

func Validate(raw json.RawMessage) error {
	var doc Document
	if err := json.Unmarshal(raw, &doc); err != nil {
		return fmt.Errorf("plan JSON: %w", err)
	}
	if doc.Floor.Bounds.Width <= 0 || doc.Floor.Bounds.Depth <= 0 {
		return fmt.Errorf("emprise au sol invalide")
	}
	if len(doc.Walls) < 4 {
		return fmt.Errorf("au moins 4 murs requis")
	}
	ids := map[string]struct{}{}
	for _, w := range doc.Walls {
		if w.ID == "" {
			return fmt.Errorf("mur sans id")
		}
		ids[w.ID] = struct{}{}
		if math.Abs(w.A.X-w.B.X) > 1e-6 && math.Abs(w.A.Y-w.B.Y) > 1e-6 {
			return fmt.Errorf("mur %s non orthogonal", w.ID)
		}
	}
	for _, r := range doc.Rooms {
		if len(r.Polygon) < 3 {
			return fmt.Errorf("pièce %s : polygone incomplet", r.ID)
		}
	}
	for _, o := range doc.Openings {
		if _, ok := ids[o.WallID]; !ok {
			return fmt.Errorf("ouverture %s : mur inconnu", o.ID)
		}
		if o.Type != "door" && o.Type != "window" {
			return fmt.Errorf("ouverture %s : type invalide", o.ID)
		}
		if o.WidthM <= 0 {
			return fmt.Errorf("ouverture %s : largeur invalide", o.ID)
		}
	}
	return nil
}
