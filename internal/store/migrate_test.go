package store

import (
	"context"
	"os"
	"testing"
)

// TestMigrateIsIdempotent checks that applying the schema twice in a row
// (e.g. two API replicas racing to migrate on startup) doesn't error — every
// statement in the schema uses IF NOT EXISTS / safe re-application.
func TestMigrateIsIdempotent(t *testing.T) {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		t.Skip("DATABASE_URL not set")
	}
	ctx := context.Background()
	db, err := Connect(ctx, dsn)
	if err != nil {
		t.Skip("database unavailable: " + err.Error())
	}
	defer db.Close()

	if err := db.Migrate(ctx); err != nil {
		t.Fatalf("first migrate: %v", err)
	}
	if err := db.Migrate(ctx); err != nil {
		t.Fatalf("second migrate (idempotency): %v", err)
	}

	// Spot-check a couple of core tables actually exist after migration.
	for _, table := range []string{"users", "orgs", "projects", "plan_revisions", "jobs", "artifacts"} {
		var n int
		if err := db.SQL.QueryRowContext(ctx, `SELECT COUNT(*) FROM information_schema.tables WHERE table_name=$1`, table).Scan(&n); err != nil {
			t.Fatal(err)
		}
		if n != 1 {
			t.Fatalf("expected table %q to exist after migrate", table)
		}
	}
}
