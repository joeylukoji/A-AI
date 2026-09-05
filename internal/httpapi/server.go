package httpapi

import (
	"context"
	"encoding/json"
	"html/template"
	"io/fs"
	"log/slog"
	"net/http"
	"time"

	"github.com/a-ai/a-ai/internal/artifact"
	"github.com/a-ai/a-ai/internal/auth"
	"github.com/a-ai/a-ai/internal/billing"
	"github.com/a-ai/a-ai/internal/config"
	"github.com/a-ai/a-ai/internal/jobs"
	"github.com/a-ai/a-ai/internal/project"
	"github.com/a-ai/a-ai/internal/storage"
	"github.com/redis/go-redis/v9"
)

type Server struct {
	cfg       config.Config
	log       *slog.Logger
	auth      *auth.Service
	projects  *project.Service
	jobs      *jobs.Service
	billing   *billing.Service
	artifacts *artifact.Service
	storage   *storage.Client
	rdb       *redis.Client
	tmpl      *template.Template
	static    fs.FS
	mux       *http.ServeMux
}

func New(
	cfg config.Config,
	log *slog.Logger,
	authSvc *auth.Service,
	projects *project.Service,
	jobsSvc *jobs.Service,
	billingSvc *billing.Service,
	artifacts *artifact.Service,
	store *storage.Client,
	rdb *redis.Client,
	tmpl *template.Template,
	static fs.FS,
) *Server {
	s := &Server{
		cfg: cfg, log: log, auth: authSvc, projects: projects, jobs: jobsSvc,
		billing: billingSvc, artifacts: artifacts, storage: store, rdb: rdb, tmpl: tmpl, static: static,
		mux: http.NewServeMux(),
	}
	s.routes()
	return s
}

func (s *Server) Handler() http.Handler {
	return s.withLogging(s.mux)
}

func (s *Server) routes() {
	s.mux.Handle("GET /static/", http.StripPrefix("/static/", http.FileServer(http.FS(s.static))))
	s.mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})

	s.mux.HandleFunc("GET /", s.handleHome)
	s.mux.HandleFunc("GET /login", s.handleLoginPage)
	s.mux.HandleFunc("POST /login", s.handleLogin)
	s.mux.HandleFunc("GET /register", s.handleRegisterPage)
	s.mux.HandleFunc("POST /register", s.handleRegister)
	s.mux.HandleFunc("POST /logout", s.handleLogout)

	s.mux.HandleFunc("GET /projects", s.requireAuth(s.handleProjectsPage))
	s.mux.HandleFunc("POST /projects", s.requireAuth(s.handleCreateProjectForm))
	s.mux.HandleFunc("GET /projects/{id}", s.requireAuth(s.handleProjectPage))
	s.mux.HandleFunc("GET /projects/{id}/3d", s.requireAuth(s.handleProject3DPage))
	s.mux.HandleFunc("GET /projects/{id}/editor", s.requireAuth(s.handleEditorPage))
	s.mux.HandleFunc("GET /projects/{id}/viewer3d", s.requireAuth(s.handleViewer3DPage))
	s.mux.HandleFunc("GET /billing", s.requireAuth(s.handleBillingPage))

	s.mux.HandleFunc("GET /api/v1/me", s.requireAuth(s.handleMe))
	s.mux.HandleFunc("GET /api/v1/projects", s.requireAuth(s.handleListProjects))
	s.mux.HandleFunc("POST /api/v1/projects", s.requireAuth(s.handleCreateProjectAPI))
	s.mux.HandleFunc("GET /api/v1/projects/{id}", s.requireAuth(s.handleGetProject))
	s.mux.HandleFunc("POST /api/v1/projects/{id}/generate", s.requireAuth(s.handleGenerate2D))
	s.mux.HandleFunc("POST /api/v1/projects/{id}/edit", s.requireAuth(s.handleEditPlan))
	s.mux.HandleFunc("POST /api/v1/projects/{id}/adapt", s.requireAuth(s.handleAdaptPlan))
	s.mux.HandleFunc("POST /api/v1/projects/{id}/generate-3d", s.requireAuth(s.handleGenerate3D))
	s.mux.HandleFunc("POST /api/v1/projects/{id}/devis", s.requireAuth(s.handleGenerateDevis))
	s.mux.HandleFunc("PUT /api/v1/projects/{id}/plan", s.requireAuth(s.handleSavePlan))
	s.mux.HandleFunc("GET /api/v1/projects/{id}/revisions", s.requireAuth(s.handleListRevisions))
	s.mux.HandleFunc("GET /api/v1/projects/{id}/preview", s.requireAuth(s.handleProjectPreview))
	s.mux.HandleFunc("GET /api/v1/projects/{id}/artifacts", s.requireAuth(s.handleListArtifacts))
	s.mux.HandleFunc("GET /api/v1/events", s.requireAuth(s.handleOrgSSE))
	s.mux.HandleFunc("GET /api/v1/projects/{id}/events", s.requireAuth(s.handleSSE))
	s.mux.HandleFunc("GET /api/v1/revisions/{id}", s.requireAuth(s.handleGetRevision))
	s.mux.HandleFunc("POST /api/v1/revisions/{id}/export", s.requireAuth(s.handleExport))
	s.mux.HandleFunc("GET /api/v1/jobs/{id}", s.requireAuth(s.handleGetJob))
	s.mux.HandleFunc("GET /api/v1/artifacts/{id}/content", s.requireAuth(s.handleArtifactContent))
	s.mux.HandleFunc("GET /api/v1/billing/usage", s.requireAuth(s.handleUsage))
	s.mux.HandleFunc("POST /api/v1/billing/checkout", s.requireAuth(s.handleCheckout))
	s.mux.HandleFunc("POST /webhooks/stripe", s.handleStripeWebhook)

	s.mux.HandleFunc("POST /internal/jobs/{id}/complete", s.handleInternalComplete)
	s.mux.HandleFunc("POST /internal/jobs/{id}/running", s.handleInternalRunning)
	s.mux.HandleFunc("POST /internal/projects/{id}/revisions", s.handleInternalSaveRevision)
	s.mux.HandleFunc("POST /internal/projects/{id}/artifacts", s.handleInternalCreateArtifact)
}

func (s *Server) withLogging(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		next.ServeHTTP(w, r)
		s.log.Info("request", "method", r.Method, "path", r.URL.Path, "dur", time.Since(start).String())
	})
}

type ctxKey int

const principalKey ctxKey = 1

func (s *Server) requireAuth(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		c, err := r.Cookie("aai_session")
		if err != nil || c.Value == "" {
			if wantsJSON(r) {
				writeErr(w, http.StatusUnauthorized, "unauthorized", "authentication required")
				return
			}
			http.Redirect(w, r, "/login", http.StatusSeeOther)
			return
		}
		p, err := s.auth.Authenticate(r.Context(), c.Value)
		if err != nil {
			if wantsJSON(r) {
				writeErr(w, http.StatusUnauthorized, "unauthorized", "invalid session")
				return
			}
			http.Redirect(w, r, "/login", http.StatusSeeOther)
			return
		}
		ctx := context.WithValue(r.Context(), principalKey, p)
		next(w, r.WithContext(ctx))
	}
}

func principal(r *http.Request) *auth.Principal {
	p, _ := r.Context().Value(principalKey).(*auth.Principal)
	return p
}

func wantsJSON(r *http.Request) bool {
	return r.Header.Get("Accept") == "application/json" ||
		len(r.URL.Path) >= 4 && r.URL.Path[:4] == "/api"
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func writeErr(w http.ResponseWriter, status int, code, msg string) {
	writeJSON(w, status, map[string]any{"error": map[string]string{"code": code, "message": msg}})
}

func (s *Server) setSessionCookie(w http.ResponseWriter, token string) {
	http.SetCookie(w, &http.Cookie{
		Name:     "aai_session",
		Value:    token,
		Path:     "/",
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
		Secure:   s.cfg.AppEnv == "production",
		Expires:  time.Now().Add(30 * 24 * time.Hour),
	})
}
