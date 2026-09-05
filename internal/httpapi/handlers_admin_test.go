package httpapi

import (
	"context"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"strings"
	"testing"

	"github.com/a-ai/a-ai/internal/admin"
	"github.com/a-ai/a-ai/internal/project"
	"github.com/a-ai/a-ai/web"
	"github.com/google/uuid"
	_ "github.com/jackc/pgx/v5/stdlib"
)

// promoteToPlatformAdmin flips users.is_platform_admin for one user, the way
// GrantPlatformAdmins does at boot from ADMIN_EMAILS.
func promoteToPlatformAdmin(t *testing.T, userID uuid.UUID) {
	t.Helper()
	db, err := sql.Open("pgx", os.Getenv("DATABASE_URL"))
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	if _, err := db.ExecContext(context.Background(),
		`UPDATE users SET is_platform_admin=true WHERE id=$1`, userID); err != nil {
		t.Fatal(err)
	}
}

// TestAdminRoutesRejectNonAdmins is the core authorisation test for the admin
// area: /admin reads plans across every organisation, so an ordinary
// authenticated tenant must never get through — and the response must not leak
// any plan data.
func TestAdminRoutesRejectNonAdmins(t *testing.T) {
	srv := idorTestServer(t)
	token, _, _ := registeredUser(t, srv.auth)

	for _, path := range []string{"/admin", "/admin/plans", "/api/v1/admin/plans"} {
		req := httptest.NewRequest(http.MethodGet, path, nil)
		req.AddCookie(&http.Cookie{Name: "aai_session", Value: token})
		rr := httptest.NewRecorder()
		srv.Handler().ServeHTTP(rr, req)

		if rr.Code == http.StatusOK {
			t.Errorf("%s: a non-admin user must not get 200 (got body %q)", path, rr.Body.String())
			continue
		}
		if strings.Contains(rr.Body.String(), "plan_document") {
			t.Errorf("%s: response leaks plan data to a non-admin", path)
		}
	}
}

// TestAdminRoutesRejectAnonymous makes sure the admin area is not reachable at
// all without a session (no information disclosure before authentication).
func TestAdminRoutesRejectAnonymous(t *testing.T) {
	srv := idorTestServer(t)
	for _, path := range []string{"/admin", "/admin/plans", "/api/v1/admin/plans"} {
		req := httptest.NewRequest(http.MethodGet, path, nil)
		rr := httptest.NewRecorder()
		srv.Handler().ServeHTTP(rr, req)
		if rr.Code == http.StatusOK {
			t.Errorf("%s: anonymous request must not get 200", path)
		}
	}
}

// TestAdminPlansAPIListsPlansAcrossOrgs verifies the feature actually works
// for a platform admin: a plan generated inside someone else's organisation
// shows up in the admin listing (that cross-org visibility is the point).
func TestAdminPlansAPIListsPlansAcrossOrgs(t *testing.T) {
	srv := idorTestServer(t)
	ctx := context.Background()

	// A tenant with a generated plan, unrelated to the admin.
	_, tenantOrg, tenantUser := registeredUser(t, srv.auth)
	proj, err := srv.projects.Create(ctx, tenantOrg, tenantUser, "Plan du locataire", "brief")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := srv.projects.SaveRevision(ctx, proj.ID, tenantUser, "ai",
		project.EmptyPlanDocument(10, 8), nil, "", nil); err != nil {
		t.Fatal(err)
	}

	adminToken, _, adminUser := registeredUser(t, srv.auth)
	promoteToPlatformAdmin(t, adminUser)

	req := httptest.NewRequest(http.MethodGet, "/api/v1/admin/plans?q=Plan+du+locataire", nil)
	req.AddCookie(&http.Cookie{Name: "aai_session", Value: adminToken})
	rr := httptest.NewRecorder()
	srv.Handler().ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("platform admin should reach the API, got %d: %s", rr.Code, rr.Body.String())
	}
	var body struct {
		Plans []struct {
			ProjectName string `json:"project_name"`
			OrgID       string `json:"org_id"`
		} `json:"plans"`
		Total int `json:"total"`
	}
	if err := json.Unmarshal(rr.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	found := false
	for _, p := range body.Plans {
		if p.ProjectName == "Plan du locataire" && p.OrgID == tenantOrg.String() {
			found = true
		}
	}
	if !found {
		t.Fatalf("admin listing should include another org's plan, got %s", rr.Body.String())
	}
}

// TestAdminPlansSearchIsParameterised feeds SQL metacharacters through the
// search box: it must come back as a normal (empty) result set, never an
// error, and never affect other rows.
func TestAdminPlansSearchIsParameterised(t *testing.T) {
	srv := idorTestServer(t)
	adminToken, _, adminUser := registeredUser(t, srv.auth)
	promoteToPlatformAdmin(t, adminUser)

	req := httptest.NewRequest(http.MethodGet,
		"/api/v1/admin/plans?q=%27%29%3B+DROP+TABLE+plan_revisions%3B+--", nil)
	req.AddCookie(&http.Cookie{Name: "aai_session", Value: adminToken})
	rr := httptest.NewRecorder()
	srv.Handler().ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("injection attempt should be handled as a plain search, got %d: %s", rr.Code, rr.Body.String())
	}
	// The table must still be there.
	if _, _, err := srv.admin.ListPlans(context.Background(), admin.ListPlansFilter{Limit: 1}); err != nil {
		t.Fatalf("plan_revisions should be intact: %v", err)
	}
}

// adminTestDB opens a second connection for the assertions that have to look
// at the database directly (promoting a user, cross-checking counters).
func adminTestDB(t *testing.T) *sql.DB {
	t.Helper()
	db, err := sql.Open("pgx", os.Getenv("DATABASE_URL"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = db.Close() })
	return db
}

// TestRequireAdminUsesDistinctStatusPerSurface pins the two halves of the
// requireAdmin contract: HTML pages 404 (the admin area is not advertised to
// ordinary tenants) and the JSON API 403 (a client that authenticated fine
// needs to know it is an authorisation failure, not a bad URL). A regression
// to 200 on either surface is a full cross-organisation data breach.
func TestRequireAdminUsesDistinctStatusPerSurface(t *testing.T) {
	srv := idorTestServer(t)
	token, _, _ := registeredUser(t, srv.auth)

	cases := []struct {
		path string
		want int
	}{
		{"/admin", http.StatusNotFound},
		{"/admin/plans", http.StatusNotFound},
		{"/admin/plans/" + uuid.NewString(), http.StatusNotFound},
		{"/admin/plans/" + uuid.NewString() + "/preview", http.StatusNotFound},
		{"/api/v1/admin/plans", http.StatusForbidden},
	}
	for _, tc := range cases {
		req := httptest.NewRequest(http.MethodGet, tc.path, nil)
		req.AddCookie(&http.Cookie{Name: "aai_session", Value: token})
		rr := httptest.NewRecorder()
		srv.Handler().ServeHTTP(rr, req)
		if rr.Code != tc.want {
			t.Errorf("%s as a non-admin: got %d, want %d (body %q)", tc.path, rr.Code, tc.want, rr.Body.String())
		}
	}
}

// TestAdminPagesRenderCompletelyForPlatformAdmin exercises the admin HTML
// pages end to end against the real templates and real data from another
// organisation. The previous tests only ever hit the JSON API, so a template
// execution error (which render reports as a 200 with a truncated body) went
// unnoticed: /admin and /admin/plans both aborted mid-tag as soon as a listed
// plan carried a compliance score.
func TestAdminPagesRenderCompletelyForPlatformAdmin(t *testing.T) {
	srv := idorTestServer(t)
	tmpl, err := web.Templates()
	if err != nil {
		t.Fatal(err)
	}
	srv.tmpl = tmpl
	ctx := context.Background()

	_, tenantOrg, tenantUser := registeredUser(t, srv.auth)
	projectName := "Villa admin " + uuid.NewString()
	proj, err := srv.projects.Create(ctx, tenantOrg, tenantUser, projectName, "brief")
	if err != nil {
		t.Fatal(err)
	}
	rev, err := srv.projects.SaveRevision(ctx, proj.ID, tenantUser, "ai",
		project.EmptyPlanDocument(10, 8), nil, "", nil)
	if err != nil {
		t.Fatal(err)
	}
	// A compliance report is what used to break the badge rendering.
	if _, err := adminTestDB(t).ExecContext(ctx,
		`UPDATE plan_revisions SET compliance=$1 WHERE id=$2`,
		`{"score":92,"grade":"A","passed":9,"total":10}`, rev.ID); err != nil {
		t.Fatal(err)
	}

	adminToken, _, adminUser := registeredUser(t, srv.auth)
	promoteToPlatformAdmin(t, adminUser)

	searchPath := "/admin/plans?q=" + url.QueryEscape(projectName)
	for _, path := range []string{"/admin", searchPath, "/admin/plans/" + rev.ID.String()} {
		req := httptest.NewRequest(http.MethodGet, path, nil)
		req.AddCookie(&http.Cookie{Name: "aai_session", Value: adminToken})
		rr := httptest.NewRecorder()
		srv.Handler().ServeHTTP(rr, req)

		if rr.Code != http.StatusOK {
			t.Fatalf("%s: got %d, want 200 (%s)", path, rr.Code, rr.Body.String())
		}
		renderedPageIsComplete(t, path, rr.Body.String())
	}

	// The searched page must actually show the other org's plan and its badge.
	req := httptest.NewRequest(http.MethodGet, searchPath, nil)
	req.AddCookie(&http.Cookie{Name: "aai_session", Value: adminToken})
	rr := httptest.NewRecorder()
	srv.Handler().ServeHTTP(rr, req)
	if !strings.Contains(rr.Body.String(), projectName) {
		t.Errorf("admin plans page should list %q across orgs", projectName)
	}
	if !strings.Contains(rr.Body.String(), "92/100") {
		t.Errorf("admin plans page should render the compliance badge, got %s", rr.Body.String())
	}
}

// TestAdminPagesEscapeCrossOrgProjectNames checks that a project name chosen
// by one tenant cannot inject markup into the administrator's browser. The
// admin pages are the one place where a tenant-controlled string is shown to
// somebody with cross-organisation privileges, so an escaping hole there is a
// stored XSS aimed straight at the highest-privileged account.
func TestAdminPagesEscapeCrossOrgProjectNames(t *testing.T) {
	srv := idorTestServer(t)
	tmpl, err := web.Templates()
	if err != nil {
		t.Fatal(err)
	}
	srv.tmpl = tmpl
	ctx := context.Background()

	marker := uuid.NewString()
	payload := `<script>alert("` + marker + `")</script>`
	_, tenantOrg, tenantUser := registeredUser(t, srv.auth)
	proj, err := srv.projects.Create(ctx, tenantOrg, tenantUser, payload, "brief")
	if err != nil {
		t.Fatal(err)
	}
	rev, err := srv.projects.SaveRevision(ctx, proj.ID, tenantUser, "ai",
		project.EmptyPlanDocument(10, 8), nil, "", nil)
	if err != nil {
		t.Fatal(err)
	}

	adminToken, _, adminUser := registeredUser(t, srv.auth)
	promoteToPlatformAdmin(t, adminUser)

	for _, path := range []string{
		"/admin/plans?q=" + url.QueryEscape(marker),
		"/admin/plans/" + rev.ID.String(),
	} {
		req := httptest.NewRequest(http.MethodGet, path, nil)
		req.AddCookie(&http.Cookie{Name: "aai_session", Value: adminToken})
		rr := httptest.NewRecorder()
		srv.Handler().ServeHTTP(rr, req)

		body := rr.Body.String()
		if rr.Code != http.StatusOK {
			t.Fatalf("%s: got %d, want 200", path, rr.Code)
		}
		if strings.Contains(body, payload) {
			t.Errorf("%s: tenant-controlled project name rendered unescaped", path)
		}
		if !strings.Contains(body, marker) {
			t.Errorf("%s: expected the (escaped) project name to appear at all", path)
		}
	}
}

// TestAdminListOrgsCountersMatchTheDatabase guards the rewrite of ListOrgs
// from four correlated sub-selects per organisation to two grouped
// aggregates: the counters must stay identical, the rows must stay unique
// (a fan-out on the subscriptions/memberships joins would double them) and
// the ordering must stay busiest-first.
func TestAdminListOrgsCountersMatchTheDatabase(t *testing.T) {
	srv := idorTestServer(t)
	ctx := context.Background()
	db := adminTestDB(t)

	// Make sure at least one organisation in the listing has real activity.
	_, orgID, userID := registeredUser(t, srv.auth)
	for range 2 {
		proj, err := srv.projects.Create(ctx, orgID, userID, "Org counters "+uuid.NewString(), "brief")
		if err != nil {
			t.Fatal(err)
		}
		for range 2 {
			if _, err := srv.projects.SaveRevision(ctx, proj.ID, userID, "ai",
				project.EmptyPlanDocument(9, 7), nil, "", nil); err != nil {
				t.Fatal(err)
			}
		}
	}

	rows, err := srv.admin.ListOrgs(ctx, 25)
	if err != nil {
		t.Fatal(err)
	}
	if len(rows) == 0 {
		t.Fatal("expected at least one organisation")
	}

	seen := map[uuid.UUID]bool{}
	previous := -1
	for _, row := range rows {
		if seen[row.OrgID] {
			t.Fatalf("organisation %s listed twice - the joins fan out", row.OrgID)
		}
		seen[row.OrgID] = true

		if previous >= 0 && row.Plans > previous {
			t.Errorf("rows are not ordered by plan count desc: %d after %d", row.Plans, previous)
		}
		previous = row.Plans

		var members, projects, plans int
		if err := db.QueryRowContext(ctx, `
			SELECT (SELECT count(*) FROM memberships m WHERE m.org_id=$1),
			       (SELECT count(*) FROM projects p WHERE p.org_id=$1),
			       (SELECT count(*) FROM plan_revisions r
			          JOIN projects p ON p.id=r.project_id WHERE p.org_id=$1)
		`, row.OrgID).Scan(&members, &projects, &plans); err != nil {
			t.Fatal(err)
		}
		if row.Members != members || row.Projects != projects || row.Plans != plans {
			t.Errorf("org %s: got members=%d projects=%d plans=%d, want %d/%d/%d",
				row.OrgID, row.Members, row.Projects, row.Plans, members, projects, plans)
		}
		if plans == 0 && row.LastPlanAt != nil {
			t.Errorf("org %s has no plan but reports LastPlanAt=%v", row.OrgID, row.LastPlanAt)
		}
		if plans > 0 && row.LastPlanAt == nil {
			t.Errorf("org %s has %d plans but reports no LastPlanAt", row.OrgID, plans)
		}
	}
}

// TestAdminPlansPaginationDoesNotDropOrRepeatRows covers the missing tiebreaker
// in the plan listing: revisions saved in quick succession can share a
// created_at, and ORDER BY created_at alone leaves their relative order
// undefined, so LIMIT/OFFSET paging could show one row twice and never show
// another. The ORDER BY now ends with r.id.
func TestAdminPlansPaginationDoesNotDropOrRepeatRows(t *testing.T) {
	srv := idorTestServer(t)
	ctx := context.Background()

	_, orgID, userID := registeredUser(t, srv.auth)
	name := "Pagination " + uuid.NewString()
	proj, err := srv.projects.Create(ctx, orgID, userID, name, "brief")
	if err != nil {
		t.Fatal(err)
	}
	const revisions = 6
	for range revisions {
		if _, err := srv.projects.SaveRevision(ctx, proj.ID, userID, "ai",
			project.EmptyPlanDocument(9, 7), nil, "", nil); err != nil {
			t.Fatal(err)
		}
	}
	// Force the exact tie the ordering has to survive.
	if _, err := adminTestDB(t).ExecContext(ctx,
		`UPDATE plan_revisions SET created_at = now() WHERE project_id=$1`, proj.ID); err != nil {
		t.Fatal(err)
	}

	seen := map[uuid.UUID]bool{}
	for offset := 0; offset < revisions; offset += 2 {
		page, total, err := srv.admin.ListPlans(ctx, admin.ListPlansFilter{
			Search: name, Limit: 2, Offset: offset,
		})
		if err != nil {
			t.Fatal(err)
		}
		if total != revisions {
			t.Fatalf("total = %d, want %d", total, revisions)
		}
		for _, row := range page {
			if seen[row.RevisionID] {
				t.Errorf("revision %s returned on two different pages", row.RevisionID)
			}
			seen[row.RevisionID] = true
		}
	}
	if len(seen) != revisions {
		t.Errorf("paging returned %d distinct revisions, want %d", len(seen), revisions)
	}
}

// TestAdminListPlansClampsUntrustedPaging checks the bounds applied to values
// that come straight from query parameters: limit and offset are attacker
// controlled on /api/v1/admin/plans, and an oversized search term would
// otherwise be ILIKE-matched against every project, org and email on the
// instance.
func TestAdminListPlansClampsUntrustedPaging(t *testing.T) {
	srv := idorTestServer(t)
	ctx := context.Background()

	rows, _, err := srv.admin.ListPlans(ctx, admin.ListPlansFilter{Limit: 100000})
	if err != nil {
		t.Fatal(err)
	}
	if len(rows) > 200 {
		t.Errorf("limit not clamped: got %d rows", len(rows))
	}

	if _, _, err := srv.admin.ListPlans(ctx, admin.ListPlansFilter{Limit: 5, Offset: -42}); err != nil {
		t.Errorf("negative offset should be clamped, got %v", err)
	}
	if _, _, err := srv.admin.ListPlans(ctx, admin.ListPlansFilter{Limit: 5, Offset: 1 << 40}); err != nil {
		t.Errorf("huge offset should be clamped, got %v", err)
	}
	if _, _, err := srv.admin.ListPlans(ctx, admin.ListPlansFilter{
		Search: strings.Repeat("a%_x", 5000), Limit: 5,
	}); err != nil {
		t.Errorf("oversized search must stay a plain (truncated) search, got %v", err)
	}
}

// TestAdminPlansPageSurvivesAnAbsurdPageNumber covers the integer overflow in
// (page-1)*adminPlansPerPage: without the clamp, page=<max int> wrapped round
// to a negative offset.
func TestAdminPlansPageSurvivesAnAbsurdPageNumber(t *testing.T) {
	srv := idorTestServer(t)
	tmpl, err := web.Templates()
	if err != nil {
		t.Fatal(err)
	}
	srv.tmpl = tmpl

	adminToken, _, adminUser := registeredUser(t, srv.auth)
	promoteToPlatformAdmin(t, adminUser)

	for _, page := range []string{"9223372036854775807", "-1", "abc"} {
		req := httptest.NewRequest(http.MethodGet, "/admin/plans?page="+page, nil)
		req.AddCookie(&http.Cookie{Name: "aai_session", Value: adminToken})
		rr := httptest.NewRecorder()
		srv.Handler().ServeHTTP(rr, req)
		if rr.Code != http.StatusOK {
			t.Errorf("page=%s: got %d, want 200 (%s)", page, rr.Code, rr.Body.String())
			continue
		}
		renderedPageIsComplete(t, "page="+page, rr.Body.String())
	}
}

// TestAdminGetPlanHandlesNullBuildingSpec is the regression test for a 500 on
// every plan detail page: plan_revisions.building_spec and .compliance are
// nullable, and GetPlan scanned them straight into json.RawMessage. Named
// []byte types are not the *[]byte that database/sql's NULL path handles, so
// the driver returned "converting NULL to json.RawMessage is unsupported" and
// both /admin/plans/{id} and its preview endpoint answered 500 for any plan
// generated without a building spec, which is the normal case.
func TestAdminGetPlanHandlesNullBuildingSpec(t *testing.T) {
	srv := idorTestServer(t)
	ctx := context.Background()

	_, orgID, userID := registeredUser(t, srv.auth)
	proj, err := srv.projects.Create(ctx, orgID, userID, "Null spec "+uuid.NewString(), "brief")
	if err != nil {
		t.Fatal(err)
	}
	rev, err := srv.projects.SaveRevision(ctx, proj.ID, userID, "ai",
		project.EmptyPlanDocument(9, 7), nil, "", nil)
	if err != nil {
		t.Fatal(err)
	}
	var spec, compliance sql.NullString
	if err := adminTestDB(t).QueryRowContext(ctx,
		`SELECT building_spec, compliance FROM plan_revisions WHERE id=$1`, rev.ID,
	).Scan(&spec, &compliance); err != nil {
		t.Fatal(err)
	}
	if spec.Valid {
		t.Fatalf("test setup: building_spec should be NULL, got %q", spec.String)
	}

	detail, err := srv.admin.GetPlan(ctx, rev.ID)
	if err != nil {
		t.Fatalf("GetPlan on a plan with a NULL building_spec: %v", err)
	}
	if detail.BuildingSpec != nil {
		t.Errorf("BuildingSpec = %s, want nil for a SQL NULL", detail.BuildingSpec)
	}
	if len(detail.PlanDocument) == 0 {
		t.Error("PlanDocument should still be populated")
	}
}
