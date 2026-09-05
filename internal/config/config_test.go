package config

import "testing"

func TestValidateAllowsDevDefaultsOutsideProduction(t *testing.T) {
	cfg := Load() // AppEnv defaults to "development"
	if err := cfg.Validate(); err != nil {
		t.Fatalf("dev config should validate, got: %v", err)
	}
}

func TestValidateRejectsDevSecretsInProduction(t *testing.T) {
	cfg := Load()
	cfg.AppEnv = "production"
	if err := cfg.Validate(); err == nil {
		t.Fatal("expected error for production config with dev-default secrets")
	}
}

func TestValidateAcceptsHardenedProductionConfig(t *testing.T) {
	cfg := Config{
		AppEnv:        "production",
		SessionSecret: "a-long-random-production-secret",
		InternalToken: "a-long-random-internal-token",
		S3AccessKey:   "AKIA-real-key",
		S3SecretKey:   "real-secret",
	}
	if err := cfg.Validate(); err != nil {
		t.Fatalf("hardened config should validate, got: %v", err)
	}
}

func TestValidateRequiresStripeWebhookSecretWhenStripeEnabled(t *testing.T) {
	cfg := Config{
		AppEnv:          "production",
		SessionSecret:   "a-long-random-production-secret",
		InternalToken:   "a-long-random-internal-token",
		S3AccessKey:     "AKIA-real-key",
		S3SecretKey:     "real-secret",
		StripeSecretKey: "sk_live_x",
	}
	if err := cfg.Validate(); err == nil {
		t.Fatal("expected error when STRIPE_SECRET_KEY is set without STRIPE_WEBHOOK_SECRET")
	}
}

// TestParseEmailListNormalises pins the parsing of ADMIN_EMAILS, the env var
// that decides who can read every organisation's plans from /admin: entries
// are trimmed and lowercased so the comparison against users.email is
// case-insensitive, blanks are dropped, and an unset/blank value yields no
// administrator at all (fail closed).
func TestParseEmailListNormalises(t *testing.T) {
	cases := []struct {
		raw  string
		want []string
	}{
		{"", nil},
		{"   ", nil},
		{",  , ,", nil},
		{"A@b.com", []string{"a@b.com"}},
		{" A@b.com , ,c@D.com ", []string{"a@b.com", "c@d.com"}},
	}
	for _, tc := range cases {
		got := parseEmailList(tc.raw)
		if len(got) != len(tc.want) {
			t.Errorf("parseEmailList(%q) = %q, want %q", tc.raw, got, tc.want)
			continue
		}
		for i := range got {
			if got[i] != tc.want[i] {
				t.Errorf("parseEmailList(%q)[%d] = %q, want %q", tc.raw, i, got[i], tc.want[i])
			}
		}
	}
}
