package plan

import (
	"fmt"
	"math"
	"sort"
)

type perimeterInterval struct {
	start float64
	end   float64
}

func coversSide(intervals []perimeterInterval, length float64) bool {
	sort.Slice(intervals, func(i, j int) bool {
		return intervals[i].start < intervals[j].start
	})
	var covered float64
	for _, interval := range intervals {
		if interval.start > covered+geometryEpsilon {
			return false
		}
		covered = math.Max(covered, interval.end)
	}
	return covered >= length-geometryEpsilon
}

// validatePerimeter checks the rectangular envelope after wall validation.
// Openings do not remove spans from their supporting wall representation.
func validatePerimeter(walls []any, bounds Point) error {
	sides := [4][]perimeterInterval{{}, {}, {}, {}}
	for index, value := range walls {
		path := fmt.Sprintf("walls[%d]", index)
		wall, err := object(value, path)
		if err != nil {
			return err
		}
		a, err := readPoint(wall["a"], path+".a", "invalid_wall_point")
		if err != nil {
			return err
		}
		b, err := readPoint(wall["b"], path+".b", "invalid_wall_point")
		if err != nil {
			return err
		}
		horizontal := perimeterInterval{start: math.Min(a.X, b.X), end: math.Max(a.X, b.X)}
		vertical := perimeterInterval{start: math.Min(a.Y, b.Y), end: math.Max(a.Y, b.Y)}
		if math.Abs(a.Y) <= geometryEpsilon && math.Abs(b.Y) <= geometryEpsilon {
			sides[0] = append(sides[0], horizontal)
		}
		if math.Abs(a.X-bounds.X) <= geometryEpsilon && math.Abs(b.X-bounds.X) <= geometryEpsilon {
			sides[1] = append(sides[1], vertical)
		}
		if math.Abs(a.Y-bounds.Y) <= geometryEpsilon && math.Abs(b.Y-bounds.Y) <= geometryEpsilon {
			sides[2] = append(sides[2], horizontal)
		}
		if math.Abs(a.X) <= geometryEpsilon && math.Abs(b.X) <= geometryEpsilon {
			sides[3] = append(sides[3], vertical)
		}
	}
	lengths := [4]float64{bounds.X, bounds.Y, bounds.X, bounds.Y}
	for side, intervals := range sides {
		if !coversSide(intervals, lengths[side]) {
			return &ValidationError{Code: "incomplete_perimeter", Path: fmt.Sprintf("walls.side[%d]", side)}
		}
	}
	return nil
}
