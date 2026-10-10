package plan

import (
	"fmt"
	"math"
	"sort"
)

func cross(a, b, c Point) float64 {
	return (b.X-a.X)*(c.Y-a.Y) - (b.Y-a.Y)*(c.X-a.X)
}

func near(a, b Point) bool {
	return math.Hypot(a.X-b.X, a.Y-b.Y) <= geometryEpsilon
}

func onSegment(point, a, b Point) bool {
	length := math.Hypot(b.X-a.X, b.Y-a.Y)
	collinear := math.Abs(cross(a, b, point)) <= geometryEpsilon*length
	xInside := point.X >= math.Min(a.X, b.X)-geometryEpsilon && point.X <= math.Max(a.X, b.X)+geometryEpsilon
	yInside := point.Y >= math.Min(a.Y, b.Y)-geometryEpsilon && point.Y <= math.Max(a.Y, b.Y)+geometryEpsilon
	return collinear && xInside && yInside
}

func segmentsTouch(a, b, c, d Point) bool {
	abc, abd := cross(a, b, c), cross(a, b, d)
	cda, cdb := cross(c, d, a), cross(c, d, b)
	oppositeAB := (abc > 0 && abd < 0) || (abc < 0 && abd > 0)
	oppositeCD := (cda > 0 && cdb < 0) || (cda < 0 && cdb > 0)
	return (oppositeAB && oppositeCD) || onSegment(c, a, b) || onSegment(d, a, b) ||
		onSegment(a, c, d) || onSegment(b, c, d)
}

func simplePolygon(points []Point, path string) ([]Point, error) {
	polygon := points
	if len(points) > 3 && near(points[0], points[len(points)-1]) {
		polygon = points[:len(points)-1]
	}
	count := len(polygon)
	if count < 3 {
		return nil, &ValidationError{Code: "invalid_room_polygon", Path: path}
	}
	for index, point := range polygon {
		next := polygon[(index+1)%count]
		if near(point, next) {
			return nil, &ValidationError{Code: "invalid_room_polygon", Path: path}
		}
		for _, other := range polygon[index+1:] {
			if near(point, other) {
				return nil, &ValidationError{Code: "invalid_room_polygon", Path: path}
			}
		}
		before := polygon[(index+count-1)%count]
		incoming := Point{X: point.X - before.X, Y: point.Y - before.Y}
		outgoing := Point{X: next.X - point.X, Y: next.Y - point.Y}
		adjacentLength := math.Max(math.Hypot(incoming.X, incoming.Y), math.Hypot(outgoing.X, outgoing.Y))
		if math.Abs(cross(before, point, next)) <= geometryEpsilon*adjacentLength {
			if incoming.X*outgoing.X+incoming.Y*outgoing.Y < 0 {
				return nil, &ValidationError{Code: "invalid_room_polygon", Path: path}
			}
		}
	}
	for first := range polygon {
		a, b := polygon[first], polygon[(first+1)%count]
		for second := first + 1; second < count; second++ {
			adjacent := second == first+1 || (first == 0 && second == count-1)
			if adjacent {
				continue
			}
			c, d := polygon[second], polygon[(second+1)%count]
			if segmentsTouch(a, b, c, d) {
				return nil, &ValidationError{Code: "invalid_room_polygon", Path: path}
			}
		}
	}
	return polygon, nil
}

func crossingOrdinates(first, second []Point) []float64 {
	ys := make([]float64, 0, len(first)+len(second))
	for _, point := range first {
		ys = append(ys, point.Y)
	}
	for _, point := range second {
		ys = append(ys, point.Y)
	}
	for i, a := range first {
		b := first[(i+1)%len(first)]
		rx, ry := b.X-a.X, b.Y-a.Y
		for j, c := range second {
			d := second[(j+1)%len(second)]
			sx, sy := d.X-c.X, d.Y-c.Y
			denominator := rx*sy - ry*sx
			if math.Abs(denominator) <= 1e-12 {
				continue
			}
			dx, dy := c.X-a.X, c.Y-a.Y
			t := (dx*sy - dy*sx) / denominator
			u := (dx*ry - dy*rx) / denominator
			if t >= 0 && t <= 1 && u >= 0 && u <= 1 {
				ys = append(ys, a.Y+t*ry)
			}
		}
	}
	sort.Float64s(ys)
	return ys
}

func intervalsAtY(polygon []Point, y float64) []perimeterInterval {
	crossings := make([]float64, 0, len(polygon))
	for index, a := range polygon {
		b := polygon[(index+1)%len(polygon)]
		upward := a.Y <= y && y < b.Y
		downward := b.Y <= y && y < a.Y
		if upward || downward {
			crossings = append(crossings, a.X+(y-a.Y)*(b.X-a.X)/(b.Y-a.Y))
		}
	}
	sort.Float64s(crossings)
	intervals := make([]perimeterInterval, 0, len(crossings)/2)
	for index := 0; index+1 < len(crossings); index += 2 {
		intervals = append(intervals, perimeterInterval{start: crossings[index], end: crossings[index+1]})
	}
	return intervals
}

// polygonIntersectionArea integrates horizontal overlap between all topology breakpoints.
func polygonIntersectionArea(first, second []Point) float64 {
	ys := crossingOrdinates(first, second)
	var area float64
	for index := 0; index+1 < len(ys); index++ {
		low, high := ys[index], ys[index+1]
		if high <= low {
			continue
		}
		y := low + (high-low)/2
		firstIntervals := intervalsAtY(first, y)
		secondIntervals := intervalsAtY(second, y)
		var rowWidth float64
		for _, a := range firstIntervals {
			for _, b := range secondIntervals {
				rowWidth += math.Max(0, math.Min(a.end, b.end)-math.Max(a.start, b.start))
			}
		}
		area += rowWidth * (high - low)
	}
	return area
}

func validateRoomOverlaps(polygons [][]Point) error {
	for first, a := range polygons {
		for second := first + 1; second < len(polygons); second++ {
			if polygonIntersectionArea(a, polygons[second]) > geometryEpsilon {
				return &ValidationError{
					Code: "overlapping_rooms",
					Path: fmt.Sprintf("rooms[%d],rooms[%d]", first, second),
				}
			}
		}
	}
	return nil
}
