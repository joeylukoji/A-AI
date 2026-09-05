package httpapi

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"html/template"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"testing/fstest"

	"github.com/a-ai/a-ai/internal/artifact"
	"github.com/a-ai/a-ai/internal/auth"
	"github.com/a-ai/a-ai/internal/billing"
	"github.com/a-ai/a-ai/internal/config"
	"github.com/a-ai/a-ai/internal/jobs"
	"github.com/a-ai/a-ai/internal/project"
	"github.com/google/uuid"
	_ "github.com/jackc/pgx/v5/stdlib"
)

// idorTestServer wires a real Server against DATABASE_URL (skipping the test
// when unavailable), with just enough of a template/static set to satisfy
// New's signature — these tests only exercise JSON API routes, never page
// rendering.
func idorTestServer(t *testing.T) *Server {
	t.Helper()
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		t.Skip("DATABASE_URL not set")
	}
	db, err := sql.Open("pgx", dsn)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = db.Close() })
	if err := db.PingContext(context.Background()); err != nil {
		t.Skip("database unavailable")
	}
	if _, err := db.ExecContext(context.Background(), `SELECT 1 FROM plan_revisions LIMIT 1`); err != nil {
		t.Skip("schema not migrated")
	}

	authSvc := auth.NewService(db)
	projects := project.NewService(db)
	jobsSvc := jobs.NewService(db, nil, "", "", slog.New(slog.NewTextHandler(io.Discard, nil)))
	billingSvc := billing.NewService(db, "", "", "")
	artifacts := artifact.NewService(db)

	tmpl := template.Must(template.New("x").Parse(`{{define "landing.html"}}ok{{end}}`))
	static := fstest.MapFS{"app.css": &fstest.MapFile{Data: []byte("body{}")}}
	cfg := config.Config{InternalToken: "tok", AppEnv: "test"}
	log := slog.New(slog.NewTextHandler(io.Discard, nil))

	return New(cfg, log, authSvc, projects, jobsSvc, billingSvc, artifacts, nil, nil, tmpl, static)
}

// registeredUser signs up a fresh user+org and returns their session token,
// org id, and user id.
func registeredUser(t *testing.T, authSvc *auth.Service) (token string, orgID, userID uuid.UUID) {
	t.Helper()
	email := "idor-" + uuid.NewString() + "@example.com"
	user, org, tok, err := authSvc.Register(context.Background(), email, "password123", "Test User", "Org "+email)
	if err != nil {
		t.Fatal(err)
	}
	return tok, org.ID, user.ID
}

func withSession(req *http.Request, token string) *http.Request {
	req.AddCookie(&http.Cookie{Name: "aai_session", Value: token})
	return req
}

// TestHandleGetRevisionIsScopedToCallerOrg is the end-to-end regression test
// for the IDOR fix on GET /api/v1/revisions/{id}: a revision id from the URL
// must never be readable by a user whose org didn't create it.
func TestHandleGetRevisionIsScopedToCallerOrg(t *testing.T) {
	srv := idorTestServer(t)
	ctx := context.Background()

	victimToken, victimOrg, victimUser := registeredUser(t, srv.auth)
	attackerToken, _, _ := registeredUser(t, srv.auth)

	proj, err := srv.projects.Create(ctx, victimOrg, victimUser, "Victim project", "brief")
	if err != nil {
		t.Fatal(err)
	}
	rev, err := srv.projects.SaveRevision(ctx, proj.ID, victimUser, "editor", project.EmptyPlanDocument(10, 8), nil, "", nil)
	if err != nil {
		t.Fatal(err)
	}

	// The victim can read their own revision.
	req := withSession(httptest.NewRequest(http.MethodGet, "/api/v1/revisions/"+rev.ID.String(), nil), victimToken)
	rr := httptest.NewRecorder()
	srv.Handler().ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("victim reading own revision: status %d body %s", rr.Code, rr.Body.String())
	}

	// The attacker, from a different org, must be refused — not handed the
	// victim's plan document.
	req = withSession(httptest.NewRequest(http.MethodGet, "/api/v1/revisions/"+rev.ID.String(), nil), attackerToken)
	rr = httptest.NewRecorder()
	srv.Handler().ServeHTTP(rr, req)
	if rr.Code != http.StatusNotFound {
		t.Fatalf("cross-org revision read: status %d (want 404), body %s", rr.Code, rr.Body.String())
	}
	if len(rr.Body.Bytes()) > 0 {
		var body map[string]any
		_ = json.Unmarshal(rr.Body.Bytes(), &body)
		if _, leaked := body["plan_document"]; leaked {
			t.Fatal("victim's plan_document leaked to a different org")
		}
	}
}

// TestHandleGetJobIsScopedToCallerOrg is the end-to-end regression test for
// the IDOR fix on GET /api/v1/jobs/{id}.
func TestHandleGetJobIsScopedToCallerOrg(t *testing.T) {
	srv := idorTestServer(t)
	ctx := context.Background()

	victimToken, victimOrg, victimUser := registeredUser(t, srv.auth)
	attackerToken, _, _ := registeredUser(t, srv.auth)

	proj, err := srv.projects.Create(ctx, victimOrg, victimUser, "Victim project", "brief")
	if err != nil {
		t.Fatal(err)
	}
	job, err := srv.jobs.Enqueue(ctx, jobs.EnqueueInput{
		OrgID: victimOrg, ProjectID: proj.ID, Type: "generate_2d",
		Input:     map[string]any{"brief": "a secret brief only the victim org should see"},
		SkipQueue: true,
	})
	if err != nil {
		t.Fatal(err)
	}

	req := withSession(httptest.NewRequest(http.MethodGet, "/api/v1/jobs/"+job.ID.String(), nil), victimToken)
	rr := httptest.NewRecorder()
	srv.Handler().ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("victim reading own job: status %d body %s", rr.Code, rr.Body.String())
	}

	req = withSession(httptest.NewRequest(http.MethodGet, "/api/v1/jobs/"+job.ID.String(), nil), attackerToken)
	rr = httptest.NewRecorder()
	srv.Handler().ServeHTTP(rr, req)
	if rr.Code != http.StatusNotFound {
		t.Fatalf("cross-org job read: status %d (want 404), body %s", rr.Code, rr.Body.String())
	}
	if bodyContains(rr.Body.Bytes(), "secret brief") {
		t.Fatal("victim's job input leaked to a different org")
	}
}

// TestHandleExportIsScopedToCallerOrg is the end-to-end regression test for
// the IDOR fix on POST /api/v1/revisions/{id}/export.
func TestHandleExportIsScopedToCallerOrg(t *testing.T) {
	srv := idorTestServer(t)
	ctx := context.Background()

	_, victimOrg, victimUser := registeredUser(t, srv.auth)
	attackerToken, _, _ := registeredUser(t, srv.auth)

	proj, err := srv.projects.Create(ctx, victimOrg, victimUser, "Victim project", "brief")
	if err != nil {
		t.Fatal(err)
	}
	rev, err := srv.projects.SaveRevision(ctx, proj.ID, victimUser, "editor", project.EmptyPlanDocument(10, 8), nil, "", nil)
	if err != nil {
		t.Fatal(err)
	}

	body, _ := json.Marshal(map[string]string{"format": "svg"})
	req := withSession(httptest.NewRequest(http.MethodPost, "/api/v1/revisions/"+rev.ID.String()+"/export", bytes.NewReader(body)), attackerToken)
	req.Header.Set("Content-Type", "application/json")
	rr := httptest.NewRecorder()
	srv.Handler().ServeHTTP(rr, req)
	// The export handler fails closed (404, revision not found for this org)
	// before ever reaching storage — must not proceed to export the victim's
	// plan for the attacker.
	if rr.Code != http.StatusNotFound {
		t.Fatalf("cross-org export: status %d (want 404), body %s", rr.Code, rr.Body.String())
	}
}

func bodyContains(b []byte, sub string) bool {
	return strings.Contains(string(b), sub)
}
