package plan

import "testing"

func TestSideCoverage(t *testing.T) {
	cases := []struct {
		name      string
		intervals []perimeterInterval
		expected  bool
	}{
		{name: "missing", intervals: []perimeterInterval{}, expected: false},
		{name: "complete", intervals: []perimeterInterval{{start: 0, end: 10}}, expected: true},
		{name: "overlapping", intervals: []perimeterInterval{
			{start: 5, end: 10}, {start: 0, end: 6}, {start: 2, end: 3},
		}, expected: true},
		{name: "gap tolerated", intervals: []perimeterInterval{
			{start: 0, end: 4}, {start: 4.0000005, end: 10},
		}, expected: true},
		{name: "gap refused", intervals: []perimeterInterval{
			{start: 0, end: 4}, {start: 4.0000015, end: 10},
		}, expected: false},
		{name: "tolerance per gap", intervals: []perimeterInterval{
			{start: 0, end: 3}, {start: 3.00000075, end: 6}, {start: 6.00000075, end: 10},
		}, expected: true},
		{name: "contained", intervals: []perimeterInterval{
			{start: 0, end: 10}, {start: 2, end: 3},
		}, expected: true},
	}
	for _, test := range cases {
		t.Run(test.name, func(t *testing.T) {
			if got := coversSide(test.intervals, 10); got != test.expected {
				t.Fatalf("coverage = %v, want %v", got, test.expected)
			}
		})
	}
}
