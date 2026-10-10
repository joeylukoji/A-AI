package plan

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"math"
)

const geometryEpsilon = 1e-6

type Point struct {
	X float64 `json:"x"`
	Y float64 `json:"y"`
}

// ValidationError identifies a violation of the shared structure/interval profile.
// Acceptance does not certify constructability or regulatory compliance.
type ValidationError struct {
	Code string
	Path string
}

func (e *ValidationError) Error() string {
	return fmt.Sprintf("%s: %q", e.Code, e.Path)
}

// Validate checks a saved document without repairing it or stripping metadata.
func Validate(raw json.RawMessage) error {
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber() // Preserve null/missing and defer numeric overflow to the field check.
	var value any
	if err := decoder.Decode(&value); err != nil {
		return &ValidationError{Code: "invalid_json", Path: "document"}
	}
	var trailing any
	if err := decoder.Decode(&trailing); err != io.EOF {
		return &ValidationError{Code: "invalid_json", Path: "document"}
	}
	doc, err := object(value, "document")
	if err != nil {
		return err
	}
	if doc["version"] != "1.0" || doc["units"] != "m" {
		return &ValidationError{Code: "invalid_header", Path: "version/units"}
	}
	bounds, err := documentBounds(doc)
	if err != nil {
		return err
	}
	walls, err := array(doc["walls"], "walls")
	if err != nil {
		return err
	}
	rooms, err := array(doc["rooms"], "rooms")
	if err != nil {
		return err
	}
	openingValue, exists := doc["openings"]
	if !exists {
		openingValue = []any{}
	}
	openings, err := array(openingValue, "openings")
	if err != nil {
		return err
	}
	lengths, err := validateWalls(walls, bounds)
	if err != nil {
		return err
	}
	if err := validatePerimeter(walls, bounds); err != nil {
		return err
	}
	polygons, err := validateRooms(rooms, bounds)
	if err != nil {
		return err
	}
	if err := validateRoomOverlaps(polygons); err != nil {
		return err
	}
	return validateOpenings(openings, lengths)
}

func validateWalls(walls []any, bounds Point) (map[string]float64, error) {
	lengths := make(map[string]float64, len(walls))
	if len(walls) < 4 {
		return lengths, &ValidationError{Code: "insufficient_walls", Path: "walls"}
	}
	seen := make(map[string]bool, len(walls))
	for index, value := range walls {
		path := fmt.Sprintf("walls[%d]", index)
		wall, err := object(value, path)
		if err != nil {
			return lengths, err
		}
		id, err := identifier(
			wall["id"],
			seen,
			"invalid_wall_id",
			path,
		)
		if err != nil {
			return lengths, err
		}
		a, err := readPoint(wall["a"], path+".a", "invalid_wall_point")
		if err != nil {
			return lengths, err
		}
		b, err := readPoint(wall["b"], path+".b", "invalid_wall_point")
		if err != nil {
			return lengths, err
		}
		dx, dy := math.Abs(b.X-a.X), math.Abs(b.Y-a.Y)
		length := math.Hypot(dx, dy)
		invalidLength := !finite(length) || length <= geometryEpsilon
		if invalidLength || math.Min(dx, dy) > geometryEpsilon {
			return lengths, &ValidationError{Code: "invalid_wall_segment", Path: path}
		}
		if !inBounds(a, bounds) || !inBounds(b, bounds) {
			return lengths, &ValidationError{Code: "point_out_of_bounds", Path: path}
		}
		lengths[id] = length
	}
	return lengths, nil
}

func validateRooms(rooms []any, bounds Point) ([][]Point, error) {
	if len(rooms) > 64 {
		return nil, &ValidationError{Code: "geometry_complexity_limit", Path: "rooms"}
	}
	seen := make(map[string]bool, len(rooms))
	polygons := make([][]Point, 0, len(rooms))
	var totalVertices int
	for index, value := range rooms {
		path := fmt.Sprintf("rooms[%d]", index)
		room, err := object(value, path)
		if err != nil {
			return nil, err
		}
		if _, err := identifier(
			room["id"],
			seen,
			"invalid_room_id",
			path,
		); err != nil {
			return nil, err
		}
		polygon, err := array(room["polygon"], path+".polygon")
		if err != nil {
			return nil, err
		}
		totalVertices += len(polygon)
		if len(polygon) > 64 || totalVertices > 256 {
			return nil, &ValidationError{Code: "geometry_complexity_limit", Path: path + ".polygon"}
		}
		if len(polygon) < 3 {
			return nil, &ValidationError{Code: "invalid_room_polygon", Path: path}
		}
		points := make([]Point, 0, len(polygon))
		for pointIndex, value := range polygon {
			pointPath := fmt.Sprintf("%s.polygon[%d]", path, pointIndex)
			point, err := readPoint(value, pointPath, "invalid_structure")
			if err != nil {
				return nil, err
			}
			if !inBounds(point, bounds) {
				return nil, &ValidationError{Code: "point_out_of_bounds", Path: pointPath}
			}
			points = append(points, point)
		}
		points, err = simplePolygon(points, path)
		if err != nil {
			return nil, err
		}
		origin := points[0]
		var twiceArea float64
		for i := 1; i+1 < len(points); i++ {
			a, b := points[i], points[i+1]
			twiceArea += (a.X-origin.X)*(b.Y-origin.Y) - (a.Y-origin.Y)*(b.X-origin.X)
		}
		if !finite(twiceArea) || math.Abs(twiceArea)/2 <= geometryEpsilon {
			return nil, &ValidationError{Code: "invalid_room_polygon", Path: path}
		}
		polygons = append(polygons, points)
	}
	return polygons, nil
}
