package project

import (
	"context"
	"database/sql"
	"encoding/json"
	"os"
	"os/exec"
	"strings"
	"testing"

	"github.com/google/uuid"
	_ "github.com/jackc/pgx/v5/stdlib"
)

// testDB returns a connected *sql.DB against DATABASE_URL, skipping the test
// when no database is available — mirrors internal/billing's integration
// test pattern so `go test ./...` stays green without a DB, while still
// exercising the real SQL against Postgres when one is present.
func testDB(t *testing.T) *sql.DB {
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
	if err := db.PingContext(context.Background()); err != nil {
		databaseUnavailable(t, "database unavailable")
	}
	if _, err := db.ExecContext(context.Background(), `SELECT 1 FROM plan_revisions LIMIT 1`); err != nil {
		databaseUnavailable(t, "schema not migrated")
	}
	return db
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

// seedOrgProjectUser inserts the minimum rows needed to own a project: an
// org, a user, and an owner membership. Returns their ids.
func seedOrgProjectUser(t *testing.T, db *sql.DB) (orgID, userID uuid.UUID) {
	t.Helper()
	ctx := context.Background()
	orgID = uuid.New()
	userID = uuid.New()
	if _, err := db.ExecContext(ctx, `INSERT INTO orgs (id, name, slug) VALUES ($1,$2,$3)`,
		orgID, "test-org", "test-org-"+orgID.String()[:8]); err != nil {
		t.Fatal(err)
	}
	if _, err := db.ExecContext(ctx, `INSERT INTO users (id, email, password_hash, name) VALUES ($1,$2,'x','Test')`,
		userID, "user-"+userID.String()[:8]+"@example.com"); err != nil {
		t.Fatal(err)
	}
	if _, err := db.ExecContext(ctx, `INSERT INTO memberships (org_id, user_id, role) VALUES ($1,$2,'owner')`,
		orgID, userID); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		_, _ = db.ExecContext(context.Background(), `DELETE FROM orgs WHERE id=$1`, orgID) // cascades
	})
	return orgID, userID
}

// TestGetRevisionForOrgIsScopedToOwningOrg is the regression test for the
// IDOR fix in httpapi.handleGetRevision / handleExport: GetRevisionForOrg
// must return the revision when it belongs to a project owned by the given
// org, and ErrNotFound (never the revision's data) for any other org —
// including a real, existing org that simply isn't the owner.
func TestGetRevisionForOrgIsScopedToOwningOrg(t *testing.T) {
	db := testDB(t)
	svc := NewService(db)
	ctx := context.Background()

	ownerOrg, ownerUser := seedOrgProjectUser(t, db)
	otherOrg, _ := seedOrgProjectUser(t, db)

	proj, err := svc.Create(ctx, ownerOrg, ownerUser, "Secret project", "brief")
	if err != nil {
		t.Fatal(err)
	}
	plan := EmptyPlanDocument(10, 8)
	rev, err := svc.SaveRevision(ctx, proj.ID, ownerUser, "editor", plan, nil, "", nil)
	if err != nil {
		t.Fatal(err)
	}

	got, err := svc.GetRevisionForOrg(ctx, ownerOrg, rev.ID)
	if err != nil {
		t.Fatalf("owning org should load the revision: %v", err)
	}
	if got.ID != rev.ID {
		t.Fatalf("got revision %s, want %s", got.ID, rev.ID)
	}

	if _, err := svc.GetRevisionForOrg(ctx, otherOrg, rev.ID); err != ErrNotFound {
		t.Fatalf("other org must not be able to load the revision (IDOR): err=%v", err)
	}

	if _, err := svc.GetRevisionForOrg(ctx, uuid.New(), rev.ID); err != ErrNotFound {
		t.Fatalf("unrelated org must not be able to load the revision: err=%v", err)
	}
}

// TestGetRevisionIsUnscoped documents that the plain GetRevision (used only
// after the caller already resolved the project through an org-scoped
// project.Get) intentionally has no org filter, and still returns the data.
func TestGetRevisionIsUnscoped(t *testing.T) {
	db := testDB(t)
	svc := NewService(db)
	ctx := context.Background()

	orgID, userID := seedOrgProjectUser(t, db)
	proj, err := svc.Create(ctx, orgID, userID, "P", "brief")
	if err != nil {
		t.Fatal(err)
	}
	rev, err := svc.SaveRevision(ctx, proj.ID, userID, "editor", EmptyPlanDocument(10, 8), nil, "", nil)
	if err != nil {
		t.Fatal(err)
	}
	got, err := svc.GetRevision(ctx, rev.ID)
	if err != nil {
		t.Fatal(err)
	}
	if got.ID != rev.ID {
		t.Fatalf("got %s, want %s", got.ID, rev.ID)
	}
}

func TestSaveRevisionDetectsConflict(t *testing.T) {
	db := testDB(t)
	svc := NewService(db)
	ctx := context.Background()

	orgID, userID := seedOrgProjectUser(t, db)
	proj, err := svc.Create(ctx, orgID, userID, "P", "brief")
	if err != nil {
		t.Fatal(err)
	}
	first, err := svc.SaveRevision(ctx, proj.ID, userID, "editor", EmptyPlanDocument(10, 8), nil, "", nil)
	if err != nil {
		t.Fatal(err)
	}
	stale := first.ID // pretend a second save happened elsewhere by rotating current_revision_id
	second, err := svc.SaveRevision(ctx, proj.ID, userID, "editor", EmptyPlanDocument(12, 9), nil, "", nil)
	if err != nil {
		t.Fatal(err)
	}
	_ = second

	if _, err := svc.SaveRevision(ctx, proj.ID, userID, "editor", EmptyPlanDocument(11, 9), nil, "", &stale); err != ErrConflict {
		t.Fatalf("expected ErrConflict against a stale base revision, got %v", err)
	}
}

func TestListRevisionsOrdersByVersionDesc(t *testing.T) {
	db := testDB(t)
	svc := NewService(db)
	ctx := context.Background()

	orgID, userID := seedOrgProjectUser(t, db)
	proj, err := svc.Create(ctx, orgID, userID, "P", "brief")
	if err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 3; i++ {
		if _, err := svc.SaveRevision(ctx, proj.ID, userID, "editor", EmptyPlanDocument(10, 8), nil, "", nil); err != nil {
			t.Fatal(err)
		}
	}
	list, err := svc.ListRevisions(ctx, proj.ID)
	if err != nil {
		t.Fatal(err)
	}
	if len(list) != 3 {
		t.Fatalf("got %d revisions, want 3", len(list))
	}
	for i, r := range list {
		if r.Version != 3-i {
			t.Fatalf("revisions not ordered by version desc: %+v", list)
		}
	}
}

func TestGetIsScopedToOrg(t *testing.T) {
	db := testDB(t)
	svc := NewService(db)
	ctx := context.Background()

	orgID, userID := seedOrgProjectUser(t, db)
	otherOrg, _ := seedOrgProjectUser(t, db)
	proj, err := svc.Create(ctx, orgID, userID, "P", "brief")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := svc.Get(ctx, orgID, proj.ID); err != nil {
		t.Fatalf("owning org should load project: %v", err)
	}
	if _, err := svc.Get(ctx, otherOrg, proj.ID); err != ErrNotFound {
		t.Fatalf("other org must not load project (IDOR): err=%v", err)
	}
}

func TestEmptyPlanDocumentIsValidJSON(t *testing.T) {
	doc := EmptyPlanDocument(10.5, 8.25)
	var v map[string]any
	if err := json.Unmarshal(doc, &v); err != nil {
		t.Fatalf("EmptyPlanDocument produced invalid JSON: %v", err)
	}
	bounds := v["floor"].(map[string]any)["bounds"].(map[string]any)
	if bounds["width"] != 10.5 || bounds["depth"] != 8.25 {
		t.Fatalf("unexpected bounds: %#v", bounds)
	}
}

// TestListRevisionSummariesReturnsFullHistory is the regression test for the
// bug where generating a new plan appeared to wipe the previous ones: every
// generation inserts a new plan_revisions row, but nothing ever listed them,
// so the UI only ever showed the current one. All versions must come back,
// newest first, with exactly one flagged as current.
func TestListRevisionSummariesReturnsFullHistory(t *testing.T) {
	db := testDB(t)
	svc := NewService(db)
	ctx := context.Background()

	orgID, userID := seedOrgProjectUser(t, db)
	proj, err := svc.Create(ctx, orgID, userID, "Historique", "brief")
	if err != nil {
		t.Fatal(err)
	}

	var revIDs []uuid.UUID
	for i := 0; i < 3; i++ {
		rev, err := svc.SaveRevision(ctx, proj.ID, userID, "ai", EmptyPlanDocument(10, 8), nil, "", nil)
		if err != nil {
			t.Fatal(err)
		}
		revIDs = append(revIDs, rev.ID)
	}

	list, err := svc.ListRevisionSummaries(ctx, proj.ID)
	if err != nil {
		t.Fatal(err)
	}
	if len(list) != 3 {
		t.Fatalf("expected all 3 generated plans in the history, got %d", len(list))
	}
	// Newest first.
	if list[0].Version != 3 || list[2].Version != 1 {
		t.Fatalf("expected versions 3,2,1 newest-first, got %d,%d,%d",
			list[0].Version, list[1].Version, list[2].Version)
	}
	current := 0
	for _, it := range list {
		if it.IsCurrent {
			current++
			if it.ID != revIDs[len(revIDs)-1] {
				t.Errorf("current revision should be the last saved one")
			}
		}
	}
	if current != 1 {
		t.Fatalf("expected exactly 1 revision flagged current, got %d", current)
	}
}

// TestSetCurrentRevisionRestoresAnOlderPlan covers the "Restaurer" button:
// an older revision can be made current again, and the history still holds
// every version afterwards (restoring must not delete anything).
func TestSetCurrentRevisionRestoresAnOlderPlan(t *testing.T) {
	db := testDB(t)
	svc := NewService(db)
	ctx := context.Background()

	orgID, userID := seedOrgProjectUser(t, db)
	proj, err := svc.Create(ctx, orgID, userID, "Restore", "brief")
	if err != nil {
		t.Fatal(err)
	}
	first, err := svc.SaveRevision(ctx, proj.ID, userID, "ai", EmptyPlanDocument(10, 8), nil, "", nil)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := svc.SaveRevision(ctx, proj.ID, userID, "ai", EmptyPlanDocument(12, 9), nil, "", nil); err != nil {
		t.Fatal(err)
	}

	if err := svc.SetCurrentRevision(ctx, orgID, proj.ID, first.ID); err != nil {
		t.Fatalf("restoring the first revision should succeed: %v", err)
	}
	got, err := svc.Get(ctx, orgID, proj.ID)
	if err != nil {
		t.Fatal(err)
	}
	if got.CurrentRevisionID == nil || *got.CurrentRevisionID != first.ID {
		t.Fatalf("current revision should be the restored one")
	}
	list, err := svc.ListRevisionSummaries(ctx, proj.ID)
	if err != nil {
		t.Fatal(err)
	}
	if len(list) != 2 {
		t.Fatalf("restoring must not drop revisions, got %d", len(list))
	}
}

// TestSetCurrentRevisionIsScopedToOrgAndProject makes sure the restore path
// can't be used as an IDOR: neither another org's request nor a revision id
// belonging to a different project may be attached to a project.
func TestSetCurrentRevisionIsScopedToOrgAndProject(t *testing.T) {
	db := testDB(t)
	svc := NewService(db)
	ctx := context.Background()

	ownerOrg, ownerUser := seedOrgProjectUser(t, db)
	otherOrg, otherUser := seedOrgProjectUser(t, db)

	victim, err := svc.Create(ctx, ownerOrg, ownerUser, "Victim", "brief")
	if err != nil {
		t.Fatal(err)
	}
	victimRev, err := svc.SaveRevision(ctx, victim.ID, ownerUser, "ai", EmptyPlanDocument(10, 8), nil, "", nil)
	if err != nil {
		t.Fatal(err)
	}
	attacker, err := svc.Create(ctx, otherOrg, otherUser, "Attacker", "brief")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := svc.SaveRevision(ctx, attacker.ID, otherUser, "ai", EmptyPlanDocument(10, 8), nil, "", nil); err != nil {
		t.Fatal(err)
	}

	if err := svc.SetCurrentRevision(ctx, otherOrg, victim.ID, victimRev.ID); err != ErrNotFound {
		t.Fatalf("another org must not restore a revision on someone else's project: err=%v", err)
	}
	// Cross-project: attacker owns the project, but the revision is the victim's.
	if err := svc.SetCurrentRevision(ctx, otherOrg, attacker.ID, victimRev.ID); err != ErrNotFound {
		t.Fatalf("a revision from another project must not be attachable: err=%v", err)
	}
	// The victim project is untouched.
	got, err := svc.Get(ctx, ownerOrg, victim.ID)
	if err != nil {
		t.Fatal(err)
	}
	if got.CurrentRevisionID == nil || *got.CurrentRevisionID != victimRev.ID {
		t.Fatal("victim project's current revision must be unchanged")
	}
}
