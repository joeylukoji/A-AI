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
