package main

import (
	"context"
	"flag"
	"io/fs"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/a-ai/a-ai/internal/artifact"
	"github.com/a-ai/a-ai/internal/auth"
	"github.com/a-ai/a-ai/internal/billing"
	"github.com/a-ai/a-ai/internal/config"
	"github.com/a-ai/a-ai/internal/httpapi"
	"github.com/a-ai/a-ai/internal/jobs"
	"github.com/a-ai/a-ai/internal/project"
	"github.com/a-ai/a-ai/internal/storage"
	"github.com/a-ai/a-ai/internal/store"
	"github.com/a-ai/a-ai/web"
	"github.com/redis/go-redis/v9"
)

func main() {
	migrateOnly := flag.Bool("migrate-only", false, "run migrations and exit")
	flag.Parse()

	cfg := config.Load()
	log := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))

	ctx := context.Background()
	db, err := store.Connect(ctx, cfg.DatabaseURL)
	if err != nil {
		log.Error("db connect", "err", err)
		os.Exit(1)
	}
	defer db.Close()

	if err := db.Migrate(ctx); err != nil {
		log.Error("migrate", "err", err)
		os.Exit(1)
	}
	if *migrateOnly {
		log.Info("migrations applied")
		return
	}

	opt, err := redis.ParseURL(cfg.RedisURL)
	if err != nil {
		log.Error("redis url", "err", err)
		os.Exit(1)
	}
	rdb := redis.NewClient(opt)
	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Warn("redis ping failed, SSE/queues degraded", "err", err)
	}

	authSvc := auth.NewService(db.SQL)
	if err := authSvc.EnsureDemoUser(ctx); err != nil {
		log.Warn("demo user", "err", err)
	}

	projects := project.NewService(db.SQL)
	jobsSvc := jobs.NewService(db.SQL, rdb, cfg.AIBaseURL, log)
	billingSvc := billing.NewService(db.SQL, cfg.StripeSecretKey, cfg.StripePricePro, cfg.StripePriceBur)
	artifacts := artifact.NewService(db.SQL)
	storeClient, err := storage.New(cfg)
	if err != nil {
		log.Error("storage", "err", err)
		os.Exit(1)
	}

	tmpl, err := web.Templates()
	if err != nil {
		log.Error("templates", "err", err)
		os.Exit(1)
	}
	staticFS, err := fs.Sub(web.Static, "static")
	if err != nil {
		log.Error("static fs", "err", err)
		os.Exit(1)
	}

	srv := httpapi.New(cfg, log, authSvc, projects, jobsSvc, billingSvc, artifacts, storeClient, rdb, tmpl, staticFS)
	httpServer := &http.Server{
		Addr:              cfg.Addr,
		Handler:           srv.Handler(),
		ReadHeaderTimeout: 10 * time.Second,
	}

	go func() {
		log.Info("api listening", "addr", cfg.Addr)
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Error("listen", "err", err)
			os.Exit(1)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	<-stop
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	_ = httpServer.Shutdown(shutdownCtx)
}
