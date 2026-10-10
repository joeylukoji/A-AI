package plan

import (
	"encoding/json"
	"math"
)

func object(value any, path string) (map[string]any, error) {
	result, ok := value.(map[string]any)
	if !ok {
		return nil, &ValidationError{Code: "invalid_structure", Path: path}
	}
	return result, nil
}

func array(value any, path string) ([]any, error) {
	result, ok := value.([]any)
	if !ok {
		return nil, &ValidationError{Code: "invalid_structure", Path: path}
	}
	return result, nil
}

func finite(value float64) bool {
	return !math.IsNaN(value) && !math.IsInf(value, 0)
}

func number(value any, path string) (float64, error) {
	raw, ok := value.(json.Number)
	if !ok {
		return 0, &ValidationError{Code: "invalid_number", Path: path}
	}
	result, err := raw.Float64()
	if err != nil || !finite(result) {
		return 0, &ValidationError{Code: "invalid_number", Path: path}
	}
	return result, nil
}

func identifier(value any, seen map[string]bool, code string, path string) (string, error) {
	id, ok := value.(string)
	if !ok || id == "" {
		return "", &ValidationError{Code: code, Path: path}
	}
	if seen[id] {
		return "", &ValidationError{Code: code, Path: path}
	}
	seen[id] = true
	return id, nil
}

func readPoint(value any, path string, shapeCode string) (Point, error) {
	point, err := object(value, path)
	if err != nil {
		return Point{}, &ValidationError{Code: shapeCode, Path: path}
	}
	x, err := number(point["x"], path+".x")
	if err != nil {
		return Point{}, err
	}
	y, err := number(point["y"], path+".y")
	if err != nil {
		return Point{}, err
	}
	return Point{X: x, Y: y}, nil
}

func inBounds(point Point, bounds Point) bool {
	xInside := point.X >= -geometryEpsilon && point.X <= bounds.X+geometryEpsilon
	yInside := point.Y >= -geometryEpsilon && point.Y <= bounds.Y+geometryEpsilon
	return xInside && yInside
}

func documentBounds(doc map[string]any) (Point, error) {
	floor, err := object(doc["floor"], "floor")
	if err != nil {
		return Point{}, err
	}
	rawBounds, err := object(floor["bounds"], "floor.bounds")
	if err != nil {
		return Point{}, err
	}
	width, err := number(rawBounds["width"], "floor.bounds.width")
	if err != nil {
		return Point{}, err
	}
	depth, err := number(rawBounds["depth"], "floor.bounds.depth")
	if err != nil {
		return Point{}, err
	}
	if width <= 0 || depth <= 0 {
		return Point{}, &ValidationError{Code: "invalid_bounds", Path: "floor.bounds"}
	}
	return Point{X: width, Y: depth}, nil
}
