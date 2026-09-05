package store

import (
	"context"
	"fmt"
	"os"
	"strings"
	"testing"
	"time"
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

// isolatedStore migrates the schema into a throwaway Postgres schema and
// returns a DB whose search_path points at it. GrantPlatformAdmins rewrites
// users.is_platform_admin for *every* row by design, so it cannot be exercised
// against the shared test database: `go test ./...` runs package binaries
// concurrently and a revoke-all would race the httpapi admin tests.
func isolatedStore(t *testing.T) *DB {
	t.Helper()
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		t.Skip("DATABASE_URL not set")
	}
	ctx := context.Background()
	base, err := Connect(ctx, dsn)
	if err != nil {
		t.Skip("database unavailable: " + err.Error())
	}
	defer base.Close()

	// Generated locally, never from user input — safe to interpolate.
	name := fmt.Sprintf("admin_test_%d", time.Now().UnixNano())
	if _, err := base.SQL.ExecContext(ctx, "CREATE SCHEMA "+name); err != nil {
		t.Skip("cannot create a test schema: " + err.Error())
	}

	sep := "?"
	if strings.Contains(dsn, "?") {
		sep = "&"
	}
	// public stays on the path so the pgcrypto/citext functions and types
	// installed there still resolve; the new schema comes first, so that is
	// where the tables land.
	db, err := Connect(ctx, dsn+sep+"search_path="+name+",public")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		_ = db.Close()
		cleanup, err := Connect(context.Background(), dsn)
		if err != nil {
			return
		}
		defer cleanup.Close()
		_, _ = cleanup.SQL.ExecContext(context.Background(), "DROP SCHEMA "+name+" CASCADE")
	})
	if err := db.Migrate(ctx); err != nil {
		t.Fatal(err)
	}
	return db
}

// TestGrantPlatformAdminsSyncsWithTheConfiguredList covers the boot-time sync
// that decides who may read every organisation's plans from /admin: the listed
// addresses get the flag, everyone else loses it (so deleting an address from
// ADMIN_EMAILS really revokes access), the match ignores case and surrounding
// whitespace, and an empty list fails closed by revoking everybody.
func TestGrantPlatformAdminsSyncsWithTheConfiguredList(t *testing.T) {
	db := isolatedStore(t)
	ctx := context.Background()

	insert := func(email string) {
		t.Helper()
		if _, err := db.SQL.ExecContext(ctx,
			`INSERT INTO users (email, password_hash, name) VALUES ($1,'x','n')`, email); err != nil {
			t.Fatal(err)
		}
	}
	isAdmin := func(email string) bool {
		t.Helper()
		var flag bool
		if err := db.SQL.QueryRowContext(ctx,
			`SELECT is_platform_admin FROM users WHERE email=$1`, email).Scan(&flag); err != nil {
			t.Fatal(err)
		}
		return flag
	}

	insert("boss@example.com")
	insert("Second.Admin@Example.COM")
	insert("tenant@example.com")

	if err := db.GrantPlatformAdmins(ctx, []string{" BOSS@example.com ", "second.admin@example.com"}); err != nil {
		t.Fatal(err)
	}
	if !isAdmin("boss@example.com") {
		t.Error("a listed address (different case, padded) should be granted the flag")
	}
	if !isAdmin("Second.Admin@Example.COM") {
		t.Error("a listed address stored in mixed case should be granted the flag")
	}
	if isAdmin("tenant@example.com") {
		t.Error("an unlisted address must never be granted the flag")
	}

	// Dropping an address from the list must revoke it, not just stop adding it.
	if err := db.GrantPlatformAdmins(ctx, []string{"second.admin@example.com"}); err != nil {
		t.Fatal(err)
	}
	if isAdmin("boss@example.com") {
		t.Error("removing an address from ADMIN_EMAILS must revoke the flag")
	}
	if !isAdmin("Second.Admin@Example.COM") {
		t.Error("a still-listed address must keep the flag")
	}

	// No list at all means no platform administrator (fail closed).
	for _, empty := range [][]string{nil, {}, {"", "   "}} {
		if err := db.GrantPlatformAdmins(ctx, empty); err != nil {
			t.Fatalf("GrantPlatformAdmins(%q): %v", empty, err)
		}
	}
	var remaining int
	if err := db.SQL.QueryRowContext(ctx,
		`SELECT count(*) FROM users WHERE is_platform_admin`).Scan(&remaining); err != nil {
		t.Fatal(err)
	}
	if remaining != 0 {
		t.Errorf("an empty ADMIN_EMAILS must leave no platform admin, got %d", remaining)
	}
}
