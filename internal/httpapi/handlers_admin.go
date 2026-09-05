package httpapi

import (
	"database/sql"
	"errors"
	"net/http"
	"strconv"

	"github.com/a-ai/a-ai/internal/admin"
	"github.com/google/uuid"
)

// requireAdmin wraps requireAuth and additionally demands the platform
// administrator flag (users.is_platform_admin, granted from ADMIN_EMAILS).
// The /admin views read across every organisation, so this is the only thing
// standing between a normal tenant and everyone else's plans: it must stay a
// hard 404/403 with no data in the response body.
//
// A 404 (not 403) is returned for non-admins on HTML pages so the existence
// of the admin area isn't advertised to ordinary users.
func (s *Server) requireAdmin(next http.HandlerFunc) http.HandlerFunc {
	return s.requireAuth(func(w http.ResponseWriter, r *http.Request) {
		p := principal(r)
		if p == nil || !p.IsPlatformAdmin {
			if wantsJSON(r) {
				writeErr(w, http.StatusForbidden, "forbidden", "platform administrator required")
				return
			}
			http.NotFound(w, r)
			return
		}
		next(w, r)
	})
}

func (s *Server) handleAdminDashboard(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	stats, err := s.admin.Stats(r.Context())
	if err != nil {
		s.log.Error("admin stats failed", "err", err)
		http.Error(w, "internal server error", http.StatusInternalServerError)
		return
	}
	orgs, err := s.admin.ListOrgs(r.Context(), 25)
	if err != nil {
		s.log.Error("admin list orgs failed", "err", err)
		http.Error(w, "internal server error", http.StatusInternalServerError)
		return
	}
	// SkipTotal: this list is a fixed "latest 15", and the global plan count
	// is already in Stats — no need for a second full-join COUNT(*).
	plans, _, err := s.admin.ListPlans(r.Context(), admin.ListPlansFilter{Limit: 15, SkipTotal: true})
	if err != nil {
		s.log.Error("admin list plans failed", "err", err)
		http.Error(w, "internal server error", http.StatusInternalServerError)
		return
	}
	// IsPlatformAdmin is injected by render() from the principal; requireAdmin
	// already guarantees it is true here.
	s.render(w, r, "admin.html", map[string]any{
		"Title": "Administration", "User": p.User, "Org": p.Org, "Role": p.Role, "Nav": "admin",
		"Stats": stats, "Orgs": orgs, "RecentPlans": plans,
	})
}

const (
	adminPlansPerPage = 50
	// maxAdminPlansPage keeps (page-1)*adminPlansPerPage well inside int range
	// and inside the offset ceiling admin.ListPlans enforces.
	maxAdminPlansPage = 2000
)

func (s *Server) handleAdminPlansPage(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	search := r.URL.Query().Get("q")
	page, _ := strconv.Atoi(r.URL.Query().Get("page"))
	// ?page=9223372036854775807 would overflow (page-1)*adminPlansPerPage into
	// a negative offset; clamp before multiplying rather than after.
	if page < 1 {
		page = 1
	}
	if page > maxAdminPlansPage {
		page = maxAdminPlansPage
	}
	rows, total, err := s.admin.ListPlans(r.Context(), admin.ListPlansFilter{
		Search: search,
		Limit:  adminPlansPerPage,
		Offset: (page - 1) * adminPlansPerPage,
	})
	if err != nil {
		s.log.Error("admin list plans failed", "err", err)
		http.Error(w, "internal server error", http.StatusInternalServerError)
		return
	}
	lastPage := (total + adminPlansPerPage - 1) / adminPlansPerPage
	if lastPage < 1 {
		lastPage = 1
	}
	s.render(w, r, "admin_plans.html", map[string]any{
		"Title": "Tous les plans", "User": p.User, "Org": p.Org, "Role": p.Role, "Nav": "admin",
		"Plans": rows, "Total": total, "Search": search,
		"Page": page, "LastPage": lastPage,
		"PrevPage": page - 1, "NextPage": page + 1,
	})
}

func (s *Server) handleAdminPlanDetail(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	id, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		http.NotFound(w, r)
		return
	}
	detail, err := s.admin.GetPlan(r.Context(), id)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			http.NotFound(w, r)
			return
		}
		s.log.Error("admin get plan failed", "revision_id", id, "err", err)
		http.Error(w, "internal server error", http.StatusInternalServerError)
		return
	}
	planJSON := "{}"
	if len(detail.PlanDocument) > 0 {
		planJSON = string(detail.PlanDocument)
	}
	s.render(w, r, "admin_plan.html", map[string]any{
		"Title": "Plan v" + strconv.Itoa(detail.Version), "User": p.User, "Org": p.Org, "Role": p.Role,
		"Nav": "admin", "Plan": detail, "PlanJSON": safeScriptJSON(planJSON),
	})
}

// handleAdminPlansAPI is the JSON counterpart of the plans table, so the data
// can be pulled programmatically (export, monitoring) without scraping HTML.
func (s *Server) handleAdminPlansAPI(w http.ResponseWriter, r *http.Request) {
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	offset, _ := strconv.Atoi(r.URL.Query().Get("offset"))
	rows, total, err := s.admin.ListPlans(r.Context(), admin.ListPlansFilter{
		Search: r.URL.Query().Get("q"),
		Limit:  limit,
		Offset: offset,
	})
	if err != nil {
		s.internalError(w, r, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"plans": rows, "total": total})
}

// handleAdminPlanPreview streams the stored preview image of any plan, so the
// admin table can show thumbnails across organisations. Mirrors the tenant
// preview endpoint but resolves the revision without an org filter (the
// requireAdmin check is what authorises it).
func (s *Server) handleAdminPlanPreview(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		http.NotFound(w, r)
		return
	}
	detail, err := s.admin.GetPlan(r.Context(), id)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			http.NotFound(w, r)
			return
		}
		s.log.Error("admin get plan failed", "revision_id", id, "err", err)
		http.Error(w, "internal server error", http.StatusInternalServerError)
		return
	}
	if detail.PreviewKey == "" || s.storage == nil {
		http.NotFound(w, r)
		return
	}
	body, contentType, err := s.storage.Get(r.Context(), detail.PreviewKey)
	if err != nil {
		s.log.Error("admin preview fetch failed", "key", detail.PreviewKey, "err", err)
		http.NotFound(w, r)
		return
	}
	if contentType == "" {
		contentType = "image/png"
	}
	w.Header().Set("Content-Type", contentType)
	// Same policy as the tenant preview endpoint: these bytes belong to another
	// organisation, so no cache may keep them around after the admin flag is
	// revoked.
	w.Header().Set("Cache-Control", "private, no-store, must-revalidate")
	_, _ = w.Write(body)
}
