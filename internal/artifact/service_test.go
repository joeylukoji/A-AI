package artifact

import (
	"context"
	"database/sql"
	"os"
	"testing"

	"github.com/google/uuid"
	_ "github.com/jackc/pgx/v5/stdlib"
)

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
	if _, err := db.ExecContext(context.Background(), `SELECT 1 FROM artifacts LIMIT 1`); err != nil {
		t.Skip("schema not migrated")
	}
	return db
}

// seedProject inserts the minimum org/user/project chain an artifact needs a
// foreign key to.
func seedProject(t *testing.T, db *sql.DB) uuid.UUID {
	t.Helper()
	ctx := context.Background()
	orgID, userID, projID := uuid.New(), uuid.New(), uuid.New()
	if _, err := db.ExecContext(ctx, `INSERT INTO orgs (id, name, slug) VALUES ($1,$2,$3)`,
		orgID, "art-org", "art-org-"+orgID.String()[:8]); err != nil {
		t.Fatal(err)
	}
	if _, err := db.ExecContext(ctx, `INSERT INTO users (id, email, password_hash, name) VALUES ($1,$2,'x','Test')`,
		userID, "art-"+userID.String()[:8]+"@example.com"); err != nil {
		t.Fatal(err)
	}
	if _, err := db.ExecContext(ctx, `INSERT INTO projects (id, org_id, name, created_by) VALUES ($1,$2,'P',$3)`,
		projID, orgID, userID); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		_, _ = db.ExecContext(context.Background(), `DELETE FROM orgs WHERE id=$1`, orgID) // cascades
	})
	return projID
}

func TestCreateGetRoundTrip(t *testing.T) {
	db := testDB(t)
	svc := NewService(db)
	ctx := context.Background()
	projID := seedProject(t, db)

	created, err := svc.Create(ctx, CreateInput{
		ProjectID:   projID,
		Kind:        "devis",
		StorageKey:  "projects/" + projID.String() + "/devis-abc.pdf",
		ContentType: "application/pdf",
		Bytes:       1234,
	})
	if err != nil {
		t.Fatal(err)
	}
	if created.ID == uuid.Nil {
		t.Fatal("expected a generated id")
	}

	got, err := svc.Get(ctx, created.ID)
	if err != nil {
		t.Fatal(err)
	}
	if got.ProjectID != projID || got.Kind != "devis" || got.Bytes != 1234 {
		t.Fatalf("round-trip mismatch: %+v", got)
	}
}

func TestGetUnknownIDReturnsErrNotFound(t *testing.T) {
	db := testDB(t)
	svc := NewService(db)
	if _, err := svc.Get(context.Background(), uuid.New()); err != ErrNotFound {
		t.Fatalf("got %v, want ErrNotFound", err)
	}
}

func TestListByProjectFiltersByKind(t *testing.T) {
	db := testDB(t)
	svc := NewService(db)
	ctx := context.Background()
	projID := seedProject(t, db)

	for _, kind := range []string{"devis", "devis", "export-svg"} {
		if _, err := svc.Create(ctx, CreateInput{
			ProjectID: projID, Kind: kind, StorageKey: "k-" + uuid.NewString(), ContentType: "application/octet-stream",
		}); err != nil {
			t.Fatal(err)
		}
	}

	all, err := svc.ListByProject(ctx, projID, "")
	if err != nil {
		t.Fatal(err)
	}
	if len(all) != 3 {
		t.Fatalf("got %d artifacts, want 3", len(all))
	}

	devis, err := svc.ListByProject(ctx, projID, "devis")
	if err != nil {
		t.Fatal(err)
	}
	if len(devis) != 2 {
		t.Fatalf("got %d devis artifacts, want 2", len(devis))
	}
	for _, a := range devis {
		if a.Kind != "devis" {
			t.Fatalf("kind filter leaked a %q artifact", a.Kind)
		}
	}
}
