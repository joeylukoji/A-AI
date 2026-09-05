package project

import (
	"context"
	"database/sql"
	"encoding/json"
	"os"
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
	return db
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
