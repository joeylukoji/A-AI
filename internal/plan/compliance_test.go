package plan

import "testing"

func goodPlanJSON() []byte {
	return []byte(`{
	  "version":"1.0","units":"m",
	  "floor":{"level":0,"height_m":2.7,"bounds":{"width":12,"depth":10}},
	  "rooms":[
	    {"id":"r1","type":"living","name":"Séjour","polygon":[{"x":0,"y":0},{"x":6,"y":0},{"x":6,"y":6},{"x":0,"y":6}]},
	    {"id":"r2","type":"kitchen","name":"Cuisine","polygon":[{"x":6,"y":0},{"x":12,"y":0},{"x":12,"y":4},{"x":6,"y":4}]},
	    {"id":"r3","type":"bedroom","name":"Chambre","polygon":[{"x":6,"y":4},{"x":12,"y":4},{"x":12,"y":10},{"x":6,"y":10}]},
	    {"id":"r4","type":"bathroom","name":"SDB","polygon":[{"x":0,"y":6},{"x":3,"y":6},{"x":3,"y":10},{"x":0,"y":10}]},
	    {"id":"r5","type":"hallway","name":"Entrée","polygon":[{"x":3,"y":6},{"x":6,"y":6},{"x":6,"y":10},{"x":3,"y":10}]}
	  ],
	  "walls":[
	    {"id":"w_outer_1","a":{"x":0,"y":0},"b":{"x":12,"y":0},"thickness_m":0.2},
	    {"id":"w_outer_2","a":{"x":12,"y":0},"b":{"x":12,"y":10},"thickness_m":0.2},
	    {"id":"w_outer_3","a":{"x":12,"y":10},"b":{"x":0,"y":10},"thickness_m":0.2},
	    {"id":"w_outer_4","a":{"x":0,"y":10},"b":{"x":0,"y":0},"thickness_m":0.2},
	    {"id":"w_i1","a":{"x":6,"y":0},"b":{"x":6,"y":6},"thickness_m":0.15},
	    {"id":"w_i2","a":{"x":0,"y":6},"b":{"x":6,"y":6},"thickness_m":0.15}
	  ],
	  "openings":[
	    {"id":"o1","wall_id":"w_outer_1","type":"door","width_m":0.9,"offset_m":1},
	    {"id":"o2","wall_id":"w_outer_2","type":"window","width_m":1.2,"offset_m":1},
	    {"id":"o3","wall_id":"w_i1","type":"door","width_m":0.8,"offset_m":0.5}
	  ]
	}`)
}

func TestEvaluateEmptyIsLow(t *testing.T) {
	out := Evaluate(nil)
	if out.Score >= 50 {
		t.Fatalf("score=%d", out.Score)
	}
	if out.Grade != "D" && out.Grade != "E" {
		t.Fatalf("grade=%s", out.Grade)
	}
	if out.Total != 15 {
		t.Fatalf("total=%d", out.Total)
	}
}

func TestEvaluateGoodPlanIsA(t *testing.T) {
	out := Evaluate(goodPlanJSON())
	if out.Score < 80 || out.Grade != "A" {
		t.Fatalf("score=%d grade=%s passed=%d/%d", out.Score, out.Grade, out.Passed, out.Total)
	}
	if out.Passed != out.Total {
		t.Fatalf("failed checks: %+v", out.Checks)
	}
}

func TestEvaluateTinyBedroomFails(t *testing.T) {
	raw := []byte(`{
	  "floor":{"height_m":2.7,"bounds":{"width":12,"depth":10}},
	  "rooms":[
	    {"type":"living","name":"Séjour","polygon":[{"x":0,"y":0},{"x":6,"y":0},{"x":6,"y":6},{"x":0,"y":6}]},
	    {"type":"bedroom","name":"Chambre","polygon":[{"x":6,"y":4},{"x":8,"y":4},{"x":8,"y":6},{"x":6,"y":6}]}
	  ],
	  "walls":[],
	  "openings":[]
	}`)
	out := Evaluate(raw)
	byKey := map[string]Check{}
	for _, c := range out.Checks {
		byKey[c.Key] = c
	}
	if byKey["bedrooms"].OK {
		t.Fatal("tiny bedroom should fail")
	}
	if out.Score == 100 {
		t.Fatal("expected score < 100")
	}
}

func TestFacadeUsesBuildingEnvelope(t *testing.T) {
	raw := []byte(`{
	  "floor":{"height_m":2.7,"bounds":{"width":16,"depth":14}},
	  "rooms":[
	    {"type":"living","name":"Séjour","polygon":[{"x":0,"y":0},{"x":6,"y":0},{"x":6,"y":6},{"x":0,"y":6}]},
	    {"type":"bedroom","name":"Chambre","polygon":[{"x":6,"y":0},{"x":10,"y":0},{"x":10,"y":6},{"x":6,"y":6}]}
	  ],
	  "walls":[],
	  "openings":[]
	}`)
	out := Evaluate(raw)
	for _, c := range out.Checks {
		if c.Key == "facade" && !c.OK {
			t.Fatalf("facade should pass on building envelope: %+v", c)
		}
	}
}

func TestInteriorHabitableFailsFacade(t *testing.T) {
	raw := []byte(`{
	  "floor":{"height_m":2.7,"bounds":{"width":12,"depth":12}},
	  "rooms":[
	    {"type":"living","name":"Séjour","polygon":[{"x":0,"y":0},{"x":12,"y":0},{"x":12,"y":4},{"x":0,"y":4}]},
	    {"type":"kitchen","name":"Cuisine","polygon":[{"x":0,"y":4},{"x":4,"y":4},{"x":4,"y":8},{"x":0,"y":8}]},
	    {"type":"bedroom","name":"Chambre","polygon":[{"x":4,"y":4},{"x":8,"y":4},{"x":8,"y":8},{"x":4,"y":8}]},
	    {"type":"bathroom","name":"SDB","polygon":[{"x":8,"y":4},{"x":12,"y":4},{"x":12,"y":8},{"x":8,"y":8}]},
	    {"type":"hallway","name":"Entrée","polygon":[{"x":0,"y":8},{"x":12,"y":8},{"x":12,"y":12},{"x":0,"y":12}]}
	  ],
	  "walls":[],
	  "openings":[]
	}`)
	out := Evaluate(raw)
	for _, c := range out.Checks {
		if c.Key == "facade" && c.OK {
			t.Fatal("interior bedroom should fail facade")
		}
	}
}
