package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)

type Config struct {
	Addr              string
	DatabaseURL       string
	RedisURL          string
	SessionSecret     string
	InternalToken     string
	AIBaseURL         string
	PublicBaseURL     string
	S3Endpoint        string
	S3AccessKey       string
	S3SecretKey       string
	S3Bucket          string
	S3UsePathStyle    bool
	StripeSecretKey   string
	StripeWebhook     string
	StripePricePro    string
	StripePriceBur    string
	AppEnv            string
	TrustProxyHeaders bool
	// GeminiOnly pauses the 2D editor and the 3D pages: users only see the
	// Gemini preview and the exports. The routes redirect to the project page.
	GeminiOnly bool
	// AdminEmails lists the platform administrators (comma-separated in
	// ADMIN_EMAILS). They are the only accounts allowed into /admin, which
	// shows plans across every organisation.
	AdminEmails []string
}

// devDefaults maps each secret-bearing field to the placeholder value shipped
// in deploy/.env.example. Validate refuses to boot in production with any of
// these still in place, since they are public knowledge (committed to the repo).
func Load() Config {
	return Config{
		Addr:              getenv("ADDR", ":8080"),
		DatabaseURL:       getenv("DATABASE_URL", "postgres://aai:aai@localhost:5432/aai?sslmode=disable"),
		RedisURL:          getenv("REDIS_URL", "redis://localhost:6379/0"),
		SessionSecret:     getenv("SESSION_SECRET", "dev-secret-change-me"),
		InternalToken:     strings.TrimSpace(getenv("INTERNAL_TOKEN", "dev-internal-token")),
		AIBaseURL:         getenv("AI_BASE_URL", "http://localhost:8000"),
		PublicBaseURL:     getenv("PUBLIC_BASE_URL", "http://localhost:8080"),
		S3Endpoint:        getenv("S3_ENDPOINT", "http://localhost:9000"),
		S3AccessKey:       getenv("S3_ACCESS_KEY", "minioadmin"),
		S3SecretKey:       getenv("S3_SECRET_KEY", "minioadmin"),
		S3Bucket:          getenv("S3_BUCKET", "aai-artifacts"),
		S3UsePathStyle:    getenvBool("S3_USE_PATH_STYLE", true),
		StripeSecretKey:   os.Getenv("STRIPE_SECRET_KEY"),
		StripeWebhook:     os.Getenv("STRIPE_WEBHOOK_SECRET"),
		StripePricePro:    os.Getenv("STRIPE_PRICE_PRO"),
		StripePriceBur:    os.Getenv("STRIPE_PRICE_BUREAU"),
		AppEnv:            getenv("APP_ENV", "development"),
		TrustProxyHeaders: getenvBool("TRUST_PROXY_HEADERS", false),
		GeminiOnly:        getenvBool("GEMINI_ONLY", false),
		AdminEmails:       parseEmailList(os.Getenv("ADMIN_EMAILS")),
	}
}

// parseEmailList splits a comma-separated ADMIN_EMAILS value, trimming blanks
// and lowercasing, so " A@b.com , ,c@d.com " yields ["a@b.com" "c@d.com"].
func parseEmailList(raw string) []string {
	if strings.TrimSpace(raw) == "" {
		return nil
	}
	parts := strings.Split(raw, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		if e := strings.ToLower(strings.TrimSpace(p)); e != "" {
			out = append(out, e)
		}
	}
	return out
}

// Validate rejects configurations that would be unsafe to run in production:
// secrets still set to the well-known development defaults committed in
// deploy/.env.example. It is a no-op outside of AppEnv=="production" so local
// dev and CI keep working without extra setup.
func (c Config) Validate() error {
	if c.AppEnv != "production" {
		return nil
	}
	var bad []string
	if c.SessionSecret == "" || c.SessionSecret == "dev-secret-change-me" || c.SessionSecret == "dev-secret-change-me-in-production" {
		bad = append(bad, "SESSION_SECRET")
	}
	if c.InternalToken == "" || c.InternalToken == "dev-internal-token" {
		bad = append(bad, "INTERNAL_TOKEN")
	}
	if c.S3AccessKey == "minioadmin" {
		bad = append(bad, "S3_ACCESS_KEY")
	}
	if c.S3SecretKey == "minioadmin" {
		bad = append(bad, "S3_SECRET_KEY")
	}
	if c.StripeSecretKey != "" && c.StripeWebhook == "" {
		bad = append(bad, "STRIPE_WEBHOOK_SECRET (required when STRIPE_SECRET_KEY is set)")
	}
	if len(bad) > 0 {
		return fmt.Errorf("refusing to start in production with insecure/missing config: %v", bad)
	}
	return nil
}

func getenv(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

func getenvBool(k string, def bool) bool {
	v := os.Getenv(k)
	if v == "" {
		return def
	}
	b, err := strconv.ParseBool(v)
	if err != nil {
		return def
	}
	return b
}
