package config

import (
	"os"
	"strconv"
)

type Config struct {
	Addr            string
	DatabaseURL     string
	RedisURL        string
	SessionSecret   string
	InternalToken   string
	AIBaseURL       string
	PublicBaseURL   string
	S3Endpoint      string
	S3AccessKey     string
	S3SecretKey     string
	S3Bucket        string
	S3UsePathStyle  bool
	StripeSecretKey string
	StripeWebhook   string
	StripePricePro  string
	StripePriceBur  string
	AppEnv          string
}

func Load() Config {
	return Config{
		Addr:            getenv("ADDR", ":8080"),
		DatabaseURL:     getenv("DATABASE_URL", "postgres://aai:aai@localhost:5432/aai?sslmode=disable"),
		RedisURL:        getenv("REDIS_URL", "redis://localhost:6379/0"),
		SessionSecret:   getenv("SESSION_SECRET", "dev-secret-change-me"),
		InternalToken:   getenv("INTERNAL_TOKEN", "dev-internal-token"),
		AIBaseURL:       getenv("AI_BASE_URL", "http://localhost:8000"),
		PublicBaseURL:   getenv("PUBLIC_BASE_URL", "http://localhost:8080"),
		S3Endpoint:      getenv("S3_ENDPOINT", "http://localhost:9000"),
		S3AccessKey:     getenv("S3_ACCESS_KEY", "minioadmin"),
		S3SecretKey:     getenv("S3_SECRET_KEY", "minioadmin"),
		S3Bucket:        getenv("S3_BUCKET", "aai-artifacts"),
		S3UsePathStyle:  getenvBool("S3_USE_PATH_STYLE", true),
		StripeSecretKey: os.Getenv("STRIPE_SECRET_KEY"),
		StripeWebhook:   os.Getenv("STRIPE_WEBHOOK_SECRET"),
		StripePricePro:  os.Getenv("STRIPE_PRICE_PRO"),
		StripePriceBur:  os.Getenv("STRIPE_PRICE_BUREAU"),
		AppEnv:          getenv("APP_ENV", "development"),
	}
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
