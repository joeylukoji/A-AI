package httpapi

import (
	"context"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"

	"github.com/a-ai/a-ai/internal/admin"
	"github.com/a-ai/a-ai/internal/project"
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
