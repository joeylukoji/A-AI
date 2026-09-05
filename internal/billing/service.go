package billing

import (
	"context"
	"database/sql"
	"errors"
	"time"

	"github.com/a-ai/a-ai/internal/domain"
	"github.com/google/uuid"
)

var ErrQuotaExceeded = errors.New("quota exceeded")

type Service struct {
	db             *sql.DB
	stripeSecret   string
	stripePricePro string
	stripePriceBur string
}

func NewService(db *sql.DB, stripeSecret, pricePro, priceBur string) *Service {
	return &Service{db: db, stripeSecret: stripeSecret, stripePricePro: pricePro, stripePriceBur: priceBur}
}

func (s *Service) GetSubscription(ctx context.Context, orgID uuid.UUID) (*domain.Subscription, error) {
	var sub domain.Subscription
	err := s.db.QueryRowContext(ctx, `
		SELECT id, org_id, plan, COALESCE(stripe_customer_id,''), COALESCE(stripe_subscription_id,''), status, current_period_end
		FROM subscriptions WHERE org_id=$1
	`, orgID).Scan(&sub.ID, &sub.OrgID, &sub.Plan, &sub.StripeCustomerID, &sub.StripeSubscriptionID, &sub.Status, &sub.CurrentPeriodEnd)
	if errors.Is(err, sql.ErrNoRows) {
		return &domain.Subscription{OrgID: orgID, Plan: "free", Status: "active"}, nil
	}
	return &sub, err
}

func periodStart(t time.Time) time.Time {
	return time.Date(t.Year(), t.Month(), 1, 0, 0, 0, 0, time.UTC)
}

func (s *Service) Usage(ctx context.Context, orgID uuid.UUID) (*domain.UsageQuota, error) {
	ps := periodStart(time.Now().UTC())
	var u domain.UsageQuota
	err := s.db.QueryRowContext(ctx, `
		SELECT org_id, period_start, generations_used, exports_used, gpu_minutes_used
		FROM usage_quotas WHERE org_id=$1 AND period_start=$2
	`, orgID, ps).Scan(&u.OrgID, &u.PeriodStart, &u.GenerationsUsed, &u.ExportsUsed, &u.GPUMinutesUsed)
	if errors.Is(err, sql.ErrNoRows) {
		return &domain.UsageQuota{OrgID: orgID, PeriodStart: ps}, nil
	}
	return &u, err
}

func (s *Service) EnsureQuota(ctx context.Context, orgID uuid.UUID, kind string) error {
	sub, err := s.GetSubscription(ctx, orgID)
	if err != nil {
		return err
	}
	limits := domain.LimitsForPlan(sub.Plan)
	usage, err := s.Usage(ctx, orgID)
	if err != nil {
		return err
	}
	switch kind {
	case "generate_2d", "generate_devis":
		if usage.GenerationsUsed >= limits.Generations {
			return ErrQuotaExceeded
		}
	case "generate_3d":
		// MVP: count 3D jobs via gpu_minutes (~0.5 each) against Generate3D limit.
		if int(usage.GPUMinutesUsed/0.5) >= limits.Generate3D {
			return ErrQuotaExceeded
		}
	case "export":
		if usage.ExportsUsed >= limits.Exports {
			return ErrQuotaExceeded
		}
	}
	return nil
}

func (s *Service) Increment(ctx context.Context, orgID uuid.UUID, kind string) error {
	ps := periodStart(time.Now().UTC())
	_, err := s.db.ExecContext(ctx, `
		INSERT INTO usage_quotas (org_id, period_start, generations_used, exports_used, gpu_minutes_used)
		VALUES ($1,$2,0,0,0)
		ON CONFLICT (org_id, period_start) DO NOTHING
	`, orgID, ps)
	if err != nil {
		return err
	}
	switch kind {
	case "generate_2d", "generate_devis":
		_, err = s.db.ExecContext(ctx, `
			UPDATE usage_quotas SET generations_used = generations_used + 1
			WHERE org_id=$1 AND period_start=$2
		`, orgID, ps)
	case "generate_3d":
		_, err = s.db.ExecContext(ctx, `
			UPDATE usage_quotas SET generations_used = generations_used + 1, gpu_minutes_used = gpu_minutes_used + 0.5
			WHERE org_id=$1 AND period_start=$2
		`, orgID, ps)
	case "export":
		_, err = s.db.ExecContext(ctx, `
			UPDATE usage_quotas SET exports_used = exports_used + 1
			WHERE org_id=$1 AND period_start=$2
		`, orgID, ps)
	}
	return err
}

func (s *Service) SetPlan(ctx context.Context, orgID uuid.UUID, plan string) error {
	_, err := s.db.ExecContext(ctx, `
		UPDATE subscriptions SET plan=$1, status='active' WHERE org_id=$2
	`, plan, orgID)
	return err
}

func (s *Service) StripeEnabled() bool {
	return s.stripeSecret != ""
}

// CheckoutURL returns a stub portal URL when Stripe is not configured.
func (s *Service) CheckoutURL(orgID uuid.UUID, plan string) string {
	if !s.StripeEnabled() {
		return "/billing?stub_checkout=" + plan
	}
	// Real Stripe Checkout would be created here.
	return "/billing?stripe=pending"
}
