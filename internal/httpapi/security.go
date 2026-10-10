package httpapi

import (
	"net"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"
)

// securityHeaders sets baseline hardening headers on every response. The CSP
// intentionally allows 'unsafe-inline' script/style and the CDNs already used
// by the templates (Google Fonts, unpkg for <model-viewer>) so it does
// not regress the current UI; it still blocks framing, plugin content and
// base-URI hijacking, which cost nothing functionally.
func (s *Server) securityHeaders(next http.Handler) http.Handler {
	csp := strings.Join([]string{
		"default-src 'self'",
		"script-src 'self' 'unsafe-inline' https://unpkg.com",
		"style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
		"img-src 'self' data: blob: https:",
		"font-src 'self' https://fonts.gstatic.com data:",
		// blob: et data: — <model-viewer> charge le GLB (et ses textures embarquées) par fetch() sur une URL
		// blob: ; sans eux le navigateur refuse la connexion et le modèle 3D ne s'affiche pas.
		"connect-src 'self' blob: data: https://unpkg.com",
		"worker-src 'self' blob:",
		"frame-ancestors 'none'",
		"base-uri 'self'",
		"object-src 'none'",
	}, "; ")
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		h := w.Header()
		h.Set("X-Content-Type-Options", "nosniff")
		h.Set("X-Frame-Options", "DENY")
		h.Set("Referrer-Policy", "strict-origin-when-cross-origin")
		h.Set("Content-Security-Policy", csp)
		h.Set("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
		if s.cfg.AppEnv == "production" {
			h.Set("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
		}
		next.ServeHTTP(w, r)
	})
}

// csrfProtect defends state-changing requests against cross-site request
// forgery. The session cookie already carries SameSite=Lax, which stops
// browsers from attaching it to cross-site POST/PUT/DELETE requests; this
// middleware adds a second, independent check (Origin/Referer must match our
// own origin) so a bug or a legacy browser that ignores SameSite doesn't
// silently remove all CSRF protection. Requests with neither header (no
// browser sends state-changing requests that way) are let through rather than
// blocked, so server-to-server calls (internal endpoints, the Stripe webhook,
// CLI/test clients) are unaffected — those paths are excluded outright below
// because they authenticate differently (internal token / webhook signature).
func (s *Server) csrfProtect(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet, http.MethodHead, http.MethodOptions:
			next.ServeHTTP(w, r)
			return
		}
		if strings.HasPrefix(r.URL.Path, "/internal/") || r.URL.Path == "/webhooks/stripe" {
			next.ServeHTTP(w, r)
			return
		}
		origin := r.Header.Get("Origin")
		if origin == "" {
			origin = r.Header.Get("Referer")
		}
		if origin != "" && !sameOrigin(origin, s.cfg.PublicBaseURL) {
			writeErr(w, http.StatusForbidden, "forbidden", "cross-origin request rejected")
			return
		}
		next.ServeHTTP(w, r)
	})
}

func sameOrigin(originHeader, base string) bool {
	ou, err := url.Parse(originHeader)
	if err != nil || ou.Host == "" {
		return false
	}
	bu, err := url.Parse(base)
	if err != nil {
		return false
	}
	return strings.EqualFold(ou.Scheme, bu.Scheme) && strings.EqualFold(ou.Host, bu.Host)
}

// rateLimiter is a simple per-key token bucket. It is intentionally
// dependency-free (no golang.org/x/time/rate) so the review stays auditable;
// it is sized for a single-process API and is not shared across replicas —
// fine for the current single-instance deployment, and cheap to swap for a
// Redis-backed limiter later if the API is horizontally scaled.
type rateLimiter struct {
	mu      sync.Mutex
	buckets map[string]*bucket
	rate    float64 // tokens refilled per second
	burst   float64 // bucket capacity
}

type bucket struct {
	tokens float64
	last   time.Time
}

func newRateLimiter(ratePerSecond, burst float64) *rateLimiter {
	rl := &rateLimiter{buckets: make(map[string]*bucket), rate: ratePerSecond, burst: burst}
	go rl.gc()
	return rl
}

func (rl *rateLimiter) allow(key string) bool {
	rl.mu.Lock()
	defer rl.mu.Unlock()
	now := time.Now()
	b, ok := rl.buckets[key]
	if !ok {
		rl.buckets[key] = &bucket{tokens: rl.burst - 1, last: now}
		return true
	}
	elapsed := now.Sub(b.last).Seconds()
	b.tokens += elapsed * rl.rate
	if b.tokens > rl.burst {
		b.tokens = rl.burst
	}
	b.last = now
	if b.tokens < 1 {
		return false
	}
	b.tokens--
	return true
}

// gc evicts idle buckets so long-running processes don't accumulate one entry
// per distinct client IP forever.
func (rl *rateLimiter) gc() {
	ticker := time.NewTicker(10 * time.Minute)
	defer ticker.Stop()
	for range ticker.C {
		cutoff := time.Now().Add(-30 * time.Minute)
		rl.mu.Lock()
		for k, b := range rl.buckets {
			if b.last.Before(cutoff) {
				delete(rl.buckets, k)
			}
		}
		rl.mu.Unlock()
	}
}

func (s *Server) rateLimit(rl *rateLimiter, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !rl.allow(s.clientIP(r)) {
			w.Header().Set("Retry-After", "10")
			writeErr(w, http.StatusTooManyRequests, "rate_limited", "too many requests, slow down")
			return
		}
		next.ServeHTTP(w, r)
	})
}

// clientIP returns the address to key rate limiting on. X-Forwarded-For is
// only trusted when TRUST_PROXY_HEADERS=1 is explicitly set (i.e. the API
// really is behind a reverse proxy/load balancer that sets it) — otherwise a
// client could forge the header to spread requests across fake identities and
// bypass the limiter entirely.
func (s *Server) clientIP(r *http.Request) string {
	if s.cfg.TrustProxyHeaders {
		if xff := r.Header.Get("X-Forwarded-For"); xff != "" {
			if i := strings.IndexByte(xff, ','); i >= 0 {
				xff = xff[:i]
			}
			if ip := strings.TrimSpace(xff); ip != "" {
				return ip
			}
		}
	}
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return r.RemoteAddr
	}
	return host
}
