package plan

import (
	"fmt"
	"math"
)

type openingSpan struct {
	start float64
	end   float64
}

func validateOpenings(openings []any, lengths map[string]float64) error {
	seen := make(map[string]bool, len(openings))
	occupied := make(map[string][]openingSpan)
	for index, value := range openings {
		path := fmt.Sprintf("openings[%d]", index)
		opening, err := object(value, path)
		if err != nil {
			return err
		}
		if _, err := identifier(
			opening["id"],
			seen,
			"invalid_opening_id",
			path,
		); err != nil {
			return err
		}
		wallID, ok := opening["wall_id"].(string)
		length, exists := lengths[wallID]
		if !ok || !exists {
			return &ValidationError{Code: "unknown_wall", Path: path}
		}
		openingType := opening["type"]
		if openingType != "door" && openingType != "window" {
			return &ValidationError{Code: "invalid_opening_type", Path: path}
		}
		if err := validateDoorSemantics(opening, openingType, path); err != nil {
			return err
		}
		start, err := number(opening["offset_m"], path+".offset_m")
		if err != nil {
			return err
		}
		width, err := number(opening["width_m"], path+".width_m")
		if err != nil {
			return err
		}
		if width <= 0 {
			return &ValidationError{Code: "invalid_opening_width", Path: path}
		}
		end := start + width
		if !finite(end) {
			return &ValidationError{Code: "invalid_number", Path: path}
		}
		if start < -geometryEpsilon || end > length+geometryEpsilon {
			return &ValidationError{Code: "opening_out_of_bounds", Path: path}
		}
		for _, previous := range occupied[wallID] {
			if math.Min(end, previous.end)-math.Max(start, previous.start) > geometryEpsilon {
				return &ValidationError{Code: "overlapping_openings", Path: path}
			}
		}
		occupied[wallID] = append(occupied[wallID], openingSpan{start: start, end: end})
	}
	return nil
}

func validateDoorSemantics(opening map[string]any, openingType any, path string) error {
	hinge, hasHinge := opening["hinge"]
	swing, hasSwing := opening["swing"]
	if openingType != "door" || hasHinge != hasSwing {
		if hasHinge || hasSwing {
			return &ValidationError{Code: "invalid_door_semantics", Path: path}
		}
		return nil
	}
	if !hasHinge {
		return nil
	}
	validHinge := hinge == "start" || hinge == "end"
	validSwing := swing == "positive" || swing == "negative"
	if !validHinge || !validSwing {
		return &ValidationError{Code: "invalid_door_semantic_value", Path: path}
	}
	return nil
}
