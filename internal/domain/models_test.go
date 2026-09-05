package domain

import "testing"

func TestLimitsForPlan(t *testing.T) {
	cases := []struct {
		plan string
		gen  int
		exp  int
		d3   int
	}{
		{"free", 5, 5, 2},
		{"pro", 50, 500, 30},
		{"bureau", 300, 5000, 200},
		{"unknown", 5, 5, 2},
	}
	for _, tc := range cases {
		got := LimitsForPlan(tc.plan)
		if got.Generations != tc.gen || got.Exports != tc.exp || got.Generate3D != tc.d3 {
			t.Fatalf("%s: got %+v", tc.plan, got)
		}
	}
}

func TestRolePermissions(t *testing.T) {
	if !RoleOwner.CanEdit() || !RoleOwner.CanBilling() {
		t.Fatal("owner should edit and bill")
	}
	if !RoleArchitect.CanEdit() || RoleArchitect.CanBilling() {
		t.Fatal("architect edit only")
	}
	if RoleViewer.CanEdit() || RoleViewer.CanBilling() {
		t.Fatal("viewer should be read-only")
	}
}
