package httpapi

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/a-ai/a-ai/internal/config"
)

func TestSameOrigin(t *testing.T) {
	cases := []struct {
		origin, base string
		want         bool
	}{
		{"https://app.example.com", "https://app.example.com", true},
		{"https://evil.com", "https://app.example.com", false},
		{"http://app.example.com", "https://app.example.com", false}, // scheme mismatch
		{"not a url", "https://app.example.com", false},
	}
	for _, c := range cases {
		if got := sameOrigin(c.origin, c.base); got != c.want {
			t.Errorf("sameOrigin(%q, %q) = %v, want %v", c.origin, c.base, got, c.want)
		}
	}
}

func TestCSRFProtectBlocksCrossOriginPost(t *testing.T) {
	s := &Server{cfg: testConfig()}
	protected := s.csrfProtect(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	req := httptest.NewRequest(http.MethodPost, "http://api.example.com/api/v1/projects", nil)
	req.Header.Set("Origin", "https://evil.example.com")
	rr := httptest.NewRecorder()
	protected.ServeHTTP(rr, req)
	if rr.Code != http.StatusForbidden {
		t.Fatalf("expected 403 for cross-origin POST, got %d", rr.Code)
	}
}

func TestCSRFProtectAllowsSameOriginPost(t *testing.T) {
	s := &Server{cfg: testConfig()}
	protected := s.csrfProtect(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	req := httptest.NewRequest(http.MethodPost, "http://api.example.com/api/v1/projects", nil)
	req.Header.Set("Origin", "http://api.example.com")
	rr := httptest.NewRecorder()
	protected.ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("expected 200 for same-origin POST, got %d", rr.Code)
	}
}

func TestCSRFProtectAllowsRequestsWithoutOriginOrReferer(t *testing.T) {
	// Non-browser clients (internal calls, tests, curl) don't send Origin/Referer;
	// they must not be locked out by this middleware.
	s := &Server{cfg: testConfig()}
	protected := s.csrfProtect(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	req := httptest.NewRequest(http.MethodPost, "http://api.example.com/api/v1/projects", nil)
	rr := httptest.NewRecorder()
	protected.ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("expected 200 when no Origin/Referer present, got %d", rr.Code)
	}
}

func TestCSRFProtectExemptsInternalAndWebhookPaths(t *testing.T) {
	s := &Server{cfg: testConfig()}
	protected := s.csrfProtect(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	for _, path := range []string{"/internal/jobs/123/complete", "/webhooks/stripe"} {
		req := httptest.NewRequest(http.MethodPost, "http://api.example.com"+path, nil)
		req.Header.Set("Origin", "https://evil.example.com")
		rr := httptest.NewRecorder()
		protected.ServeHTTP(rr, req)
		if rr.Code != http.StatusOK {
			t.Errorf("expected %s to be exempt from CSRF check, got %d", path, rr.Code)
		}
	}
}

func TestRateLimiterAllowsBurstThenBlocks(t *testing.T) {
	rl := newRateLimiter(0.001, 3) // effectively no refill within the test
	for i := 0; i < 3; i++ {
		if !rl.allow("k") {
			t.Fatalf("expected request %d to be allowed within burst", i)
		}
	}
	if rl.allow("k") {
		t.Fatal("expected 4th request to be rate limited")
	}
	// A different key has its own independent bucket.
	if !rl.allow("other") {
		t.Fatal("expected a different key to have its own bucket")
	}
}

func TestSecurityHeadersSet(t *testing.T) {
	s := &Server{cfg: testConfig()}
	h := s.securityHeaders(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, req)

	for _, header := range []string{"X-Content-Type-Options", "X-Frame-Options", "Content-Security-Policy", "Referrer-Policy"} {
		if rr.Header().Get(header) == "" {
			t.Errorf("expected header %s to be set", header)
		}
	}
}

// <model-viewer> charge le GLB par fetch() sur une URL blob: ; sans blob: (et data: pour les textures embarquées)
// dans connect-src le navigateur refuse la connexion et la maquette 3D ne s'affiche pas.
func TestCSPLetsTheModelViewerLoadItsGLB(t *testing.T) {
	s := &Server{cfg: testConfig()}
	h := s.securityHeaders(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusOK) }))
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/", nil))
	var connect string
	for _, directive := range strings.Split(rr.Header().Get("Content-Security-Policy"), ";") {
		if d := strings.TrimSpace(directive); strings.HasPrefix(d, "connect-src ") {
			connect = d
		}
	}
	for _, source := range []string{"'self'", "blob:", "data:", "https://unpkg.com"} {
		if !strings.Contains(connect, source) {
			t.Errorf("connect-src %q should allow %s", connect, source)
		}
	}
	if strings.Contains(connect, "*") || strings.Contains(connect, "http:") {
		t.Errorf("connect-src %q is too permissive", connect)
	}
}

func testConfig() config.Config {
	return config.Config{PublicBaseURL: "http://api.example.com", AppEnv: "test"}
}
