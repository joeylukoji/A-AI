package plan

import "testing"

func TestValidateOK(t *testing.T) {
	raw := []byte(`{
	  "version":"1.0","units":"m",
	  "floor":{"level":0,"height_m":2.7,"bounds":{"width":10,"depth":8}},
	  "walls":[
	    {"id":"w1","a":{"x":0,"y":0},"b":{"x":10,"y":0},"thickness_m":0.2},
	    {"id":"w2","a":{"x":10,"y":0},"b":{"x":10,"y":8},"thickness_m":0.2},
	    {"id":"w3","a":{"x":10,"y":8},"b":{"x":0,"y":8},"thickness_m":0.2},
	    {"id":"w4","a":{"x":0,"y":8},"b":{"x":0,"y":0},"thickness_m":0.2}
	  ],
	  "rooms":[{"id":"r1","type":"living","polygon":[{"x":0,"y":0},{"x":5,"y":0},{"x":5,"y":4}]}],
	  "openings":[{"id":"o1","wall_id":"w1","type":"door","offset_m":1,"width_m":0.9}]
	}`)
	if err := Validate(raw); err != nil {
		t.Fatal(err)
	}
}

func TestValidateRejectsUnknownWall(t *testing.T) {
	raw := []byte(`{
	  "floor":{"bounds":{"width":10,"depth":8}},
	  "walls":[
	    {"id":"w1","a":{"x":0,"y":0},"b":{"x":10,"y":0}},
	    {"id":"w2","a":{"x":10,"y":0},"b":{"x":10,"y":8}},
	    {"id":"w3","a":{"x":10,"y":8},"b":{"x":0,"y":8}},
	    {"id":"w4","a":{"x":0,"y":8},"b":{"x":0,"y":0}}
	  ],
	  "rooms":[],
	  "openings":[{"id":"o1","wall_id":"missing","type":"door","width_m":0.9}]
	}`)
	if err := Validate(raw); err == nil {
		t.Fatal("expected error")
	}
}
