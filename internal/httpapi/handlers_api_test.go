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
	"os/exec"
	"strings"
	"sync"
	"testing"
	"testing/fstest"
	"time"

	"github.com/a-ai/a-ai/internal/admin"
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
	server, _ := postgresTestServer(t, "")
	return server
}

func postgresTestServer(t *testing.T, aiURL string) (*Server, *sql.DB) {
	t.Helper()
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		databaseUnavailable(t, "DATABASE_URL not set")
	}
	db, err := sql.Open("pgx", dsn)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = db.Close() })
	pingCtx, cancelPing := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancelPing()
	if err := db.PingContext(pingCtx); err != nil {
		databaseUnavailable(t, "database unavailable")
	}
	if _, err := db.ExecContext(pingCtx, `SELECT 1 FROM plan_revisions LIMIT 1`); err != nil {
		databaseUnavailable(t, "schema not migrated")
	}

	authSvc := auth.NewService(db, nil)
	projects := project.NewService(db)
	jobsSvc := jobs.NewService(db, nil, aiURL, "tok", slog.New(slog.NewTextHandler(io.Discard, nil)))
	billingSvc := billing.NewService(db, "", "", "")
	artifacts := artifact.NewService(db)

	tmpl := template.Must(template.New("x").Parse(`{{define "landing.html"}}ok{{end}}`))
	static := fstest.MapFS{"app.css": &fstest.MapFile{Data: []byte("body{}")}}
	cfg := config.Config{InternalToken: "tok", AppEnv: "test"}
	log := slog.New(slog.NewTextHandler(io.Discard, nil))

	server := New(cfg, log, authSvc, projects, jobsSvc, billingSvc, artifacts, admin.NewService(db), nil, nil, tmpl, static)
	return server, db
}

func databaseUnavailable(t *testing.T, reason string) {
	t.Helper()
	if databaseTestsRequired() {
		t.Fatalf("PostgreSQL integration tests are required but unavailable: %s", reason)
	}
	t.Skip(reason)
}

func databaseTestsRequired() bool {
	return os.Getenv("REQUIRE_DATABASE_TESTS") == "1"
}

func TestDatabaseUnavailableProbe(t *testing.T) {
	if os.Getenv("AAI_DATABASE_UNAVAILABLE_PROBE") != "1" {
		return
	}
	databaseUnavailable(t, "probe reason")
}

func TestDatabaseUnavailableOutcomes(t *testing.T) {
	for _, tc := range []struct {
		name     string
		value    string
		want     string
		wantFail bool
	}{
		{name: "local mode skips", value: "", want: "--- SKIP: TestDatabaseUnavailableProbe"},
		{name: "required mode fails", value: "1", want: "PostgreSQL integration tests are required but unavailable: probe reason", wantFail: true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			command := exec.Command(os.Args[0], "-test.v", "-test.run=^TestDatabaseUnavailableProbe$")
			for _, entry := range os.Environ() {
				if strings.HasPrefix(entry, "REQUIRE_DATABASE_TESTS=") || strings.HasPrefix(entry, "AAI_DATABASE_UNAVAILABLE_PROBE=") {
					continue
				}
				command.Env = append(command.Env, entry)
			}
			command.Env = append(command.Env, "REQUIRE_DATABASE_TESTS="+tc.value, "AAI_DATABASE_UNAVAILABLE_PROBE=1")
			output, err := command.CombinedOutput()
			if (err != nil) != tc.wantFail || !strings.Contains(string(output), tc.want) {
				t.Fatalf("probe error = %v, output = %s; want failure=%t and output containing %q", err, output, tc.wantFail, tc.want)
			}
		})
	}
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

func TestEditJobRejectsStaleRevisionAfterConcurrentEditorSave(t *testing.T) {
	enteredAI := make(chan struct{}, 1)
	releaseAI := make(chan struct{})
	var releaseOnce sync.Once
	var srv *Server
	var jobID uuid.UUID

	ai := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/edit" {
			http.NotFound(w, r)
			return
		}
		if r.Header.Get("X-Internal-Token") != "tok" {
			http.Error(w, "missing internal token", http.StatusUnauthorized)
			return
		}
		var request struct {
			Instruction string `json:"instruction"`
		}
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			http.Error(w, "invalid request", http.StatusBadRequest)
			return
		}
		if request.Instruction != "ajoute un espace" {
			http.Error(w, "unexpected instruction", http.StatusBadRequest)
			return
		}
		enteredAI <- struct{}{}
		<-releaseAI

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"plan_document": project.EmptyPlanDocument(14, 9),
			"building_spec": map[string]any{},
			"reply_fr":      "Plan modifié.",
			"edit_status":   "applied",
			"clarify":       false,
		})
	}))
	defer func() {
		releaseOnce.Do(func() { close(releaseAI) })
		ai.Close()
		if srv == nil || jobID == uuid.Nil {
			return
		}
		waitCtx, cancelWait := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancelWait()
		lastStatus := "unknown"
		for {
			job, err := srv.jobs.Get(waitCtx, jobID)
			if err == nil {
				lastStatus = job.Status
				if job.Status == "failed" || job.Status == "succeeded" {
					return
				}
			}
			select {
			case <-time.After(25 * time.Millisecond):
			case <-waitCtx.Done():
				t.Errorf("edit worker did not stop before test cleanup: last status %q, error %v", lastStatus, err)
				return
			}
		}
	}()

	var db *sql.DB
	srv, db = postgresTestServer(t, ai.URL)
	ctx, cancelTest := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancelTest()
	email := "cas-" + uuid.NewString() + "@example.com"
	user, org, token, err := srv.auth.Register(ctx, email, "password123", "CAS Tester", "CAS integration "+email)
	if err != nil {
		t.Fatal(err)
	}
	orgID, userID := org.ID, user.ID
	t.Cleanup(func() {
		_, _ = db.ExecContext(context.Background(), `DELETE FROM orgs WHERE id=$1`, orgID)
		_, _ = db.ExecContext(context.Background(), `DELETE FROM users WHERE id=$1`, userID)
	})
	proj, err := srv.projects.Create(ctx, orgID, userID, "CAS integration", "Maison")
	if err != nil {
		t.Fatal(err)
	}
	base, err := srv.projects.SaveRevision(
		ctx,
		proj.ID,
		userID,
		"editor",
		project.EmptyPlanDocument(10, 8),
		nil,
		"",
		nil,
	)
	if err != nil {
		t.Fatal(err)
	}

	requestBody, err := json.Marshal(map[string]string{"instruction": "ajoute un espace"})
	if err != nil {
		t.Fatal(err)
	}
	request := withSession(httptest.NewRequestWithContext(
		ctx,
		http.MethodPost,
		"/api/v1/projects/"+proj.ID.String()+"/edit",
		bytes.NewReader(requestBody),
	), token)
	request.Header.Set("Content-Type", "application/json")
	response := httptest.NewRecorder()
	srv.Handler().ServeHTTP(response, request)
	if response.Code != http.StatusAccepted {
		t.Fatalf("edit request: status %d, body %s", response.Code, response.Body.String())
	}
	var accepted struct {
		JobID uuid.UUID `json:"job_id"`
	}
	if err := json.Unmarshal(response.Body.Bytes(), &accepted); err != nil {
		t.Fatal(err)
	}
	if accepted.JobID == uuid.Nil {
		t.Fatal("edit response did not include a job_id")
	}
	jobID = accepted.JobID

	select {
	case <-enteredAI:
	case <-time.After(5 * time.Second):
		t.Fatal("edit worker did not reach the fake AI service")
	}

	concurrentPlan := project.EmptyPlanDocument(12, 9)
	concurrent, err := srv.projects.SaveRevision(
		ctx,
		proj.ID,
		userID,
		"editor",
		concurrentPlan,
		nil,
		"",
		&base.ID,
	)
	if err != nil {
		t.Fatal(err)
	}
	releaseOnce.Do(func() { close(releaseAI) })

	deadline := time.NewTimer(5 * time.Second)
	defer deadline.Stop()
	ticker := time.NewTicker(25 * time.Millisecond)
	defer ticker.Stop()
	var job struct {
		Status string `json:"status"`
		Error  string `json:"error"`
	}
	for {
		jobRequest := withSession(httptest.NewRequestWithContext(
			ctx,
			http.MethodGet,
			"/api/v1/jobs/"+accepted.JobID.String(),
			nil,
		), token)
		jobResponse := httptest.NewRecorder()
		srv.Handler().ServeHTTP(jobResponse, jobRequest)
		if jobResponse.Code != http.StatusOK {
			t.Fatalf("job status request: status %d, body %s", jobResponse.Code, jobResponse.Body.String())
		}
		if err := json.Unmarshal(jobResponse.Body.Bytes(), &job); err != nil {
			t.Fatal(err)
		}
		if job.Status == "failed" || job.Status == "succeeded" {
			break
		}
		select {
		case <-ticker.C:
		case <-deadline.C:
			t.Fatalf("edit job did not finish; last status %q", job.Status)
		}
	}
	if job.Status != "failed" {
		t.Fatalf("edit job status = %q, want failed", job.Status)
	}
	if job.Error != "revision_conflict" {
		t.Fatalf("edit job error = %q, want revision_conflict", job.Error)
	}

	currentProject, err := srv.projects.Get(ctx, orgID, proj.ID)
	if err != nil {
		t.Fatal(err)
	}
	if currentProject.CurrentRevisionID == nil || *currentProject.CurrentRevisionID != concurrent.ID {
		t.Fatalf("current revision = %v, want the concurrent editor revision %s", currentProject.CurrentRevisionID, concurrent.ID)
	}
	if currentProject.Status != "ready" {
		t.Fatalf("project status = %q, want ready after conflict", currentProject.Status)
	}
	revisions, err := srv.projects.ListRevisions(ctx, proj.ID)
	if err != nil {
		t.Fatal(err)
	}
	if len(revisions) != 2 {
		t.Fatalf("revision count = %d, want baseline plus concurrent editor save only", len(revisions))
	}
	if !planDocumentsEqual(revisions[0].PlanDocument, concurrentPlan) {
		t.Fatalf("current plan document changed after stale AI result: got %s, want %s", revisions[0].PlanDocument, concurrentPlan)
	}
}

func planDocumentsEqual(left, right []byte) bool {
	var leftValue, rightValue any
	if err := json.Unmarshal(left, &leftValue); err != nil {
		return false
	}
	if err := json.Unmarshal(right, &rightValue); err != nil {
		return false
	}
	leftJSON, err := json.Marshal(leftValue)
	if err != nil {
		return false
	}
	rightJSON, err := json.Marshal(rightValue)
	if err != nil {
		return false
	}
	return bytes.Equal(leftJSON, rightJSON)
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
