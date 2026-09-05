package billing

import (
	"context"
	"database/sql"
	"errors"
	"os"
	"testing"
	"time"

	"github.com/google/uuid"
	_ "github.com/jackc/pgx/v5/stdlib"
)

func TestStripeEnabled(t *testing.T) {
	s := NewService(nil, "", "", "")
	if s.StripeEnabled() {
		t.Fatal("expected disabled")
	}
	s = NewService(nil, "sk_test", "", "")
	if !s.StripeEnabled() {
		t.Fatal("expected enabled")
	}
}

func TestCheckoutURLStub(t *testing.T) {
	s := NewService(nil, "", "", "")
	url := s.CheckoutURL(uuid.New(), "pro")
	if url != "/billing?stub_checkout=pro" {
		t.Fatalf("unexpected url %s", url)
	}
}

func TestPeriodStart(t *testing.T) {
	ts := time.Date(2026, 8, 15, 12, 0, 0, 0, time.UTC)
	ps := periodStart(ts)
	if ps.Day() != 1 || ps.Month() != time.August {
		t.Fatalf("bad period start %v", ps)
	}
}

func TestEnsureQuotaWithDB(t *testing.T) {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		t.Skip("DATABASE_URL not set")
	}
	db, err := sql.Open("pgx", dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	ctx := context.Background()
	if err := db.PingContext(ctx); err != nil {
		t.Skip("database unavailable")
	}
	if _, err := db.ExecContext(ctx, `SELECT 1 FROM subscriptions LIMIT 1`); err != nil {
		t.Skip("schema not migrated")
	}

	s := NewService(db, "", "", "")
	orgID := uuid.New()
	_, err = db.ExecContext(ctx, `INSERT INTO orgs (id, name, slug) VALUES ($1,$2,$3)`, orgID, "quota-test", "quota-"+orgID.String()[:8])
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		_, _ = db.ExecContext(ctx, `DELETE FROM usage_quotas WHERE org_id=$1`, orgID)
		_, _ = db.ExecContext(ctx, `DELETE FROM subscriptions WHERE org_id=$1`, orgID)
		_, _ = db.ExecContext(ctx, `DELETE FROM orgs WHERE id=$1`, orgID)
	})
	_, err = db.ExecContext(ctx, `INSERT INTO subscriptions (org_id, plan, status) VALUES ($1,'free','active')`, orgID)
	if err != nil {
		t.Fatal(err)
	}

	if err := s.EnsureQuota(ctx, orgID, "generate_2d"); err != nil {
		t.Fatalf("first generate should pass: %v", err)
	}
	for i := 0; i < 5; i++ {
		if err := s.Increment(ctx, orgID, "generate_2d"); err != nil {
			t.Fatal(err)
		}
	}
	if err := s.EnsureQuota(ctx, orgID, "generate_2d"); !errors.Is(err, ErrQuotaExceeded) {
		t.Fatalf("expected quota exceeded, got %v", err)
	}
}
