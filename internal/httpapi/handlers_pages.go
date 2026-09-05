package httpapi

import (
	"encoding/json"
	"html/template"
	"net/http"

	"github.com/a-ai/a-ai/internal/billing"
	"github.com/a-ai/a-ai/internal/domain"
	"github.com/a-ai/a-ai/internal/plan"
	"github.com/google/uuid"
)

func (s *Server) render(w http.ResponseWriter, name string, data any) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if err := s.tmpl.ExecuteTemplate(w, name, data); err != nil {
		s.log.Error("template", "name", name, "err", err)
		http.Error(w, "template error", http.StatusInternalServerError)
	}
}

func (s *Server) handleHome(w http.ResponseWriter, r *http.Request) {
	if c, err := r.Cookie("aai_session"); err == nil && c.Value != "" {
		if _, err := s.auth.Authenticate(r.Context(), c.Value); err == nil {
			http.Redirect(w, r, "/projects", http.StatusSeeOther)
			return
		}
	}
	s.render(w, "landing.html", map[string]any{"Title": "A-AI"})
}

func (s *Server) handleLoginPage(w http.ResponseWriter, r *http.Request) {
	s.render(w, "login.html", map[string]any{"Title": "Connexion"})
}

func (s *Server) handleRegisterPage(w http.ResponseWriter, r *http.Request) {
	s.render(w, "register.html", map[string]any{"Title": "Inscription"})
}

func (s *Server) handleLogin(w http.ResponseWriter, r *http.Request) {
	_ = r.ParseForm()
	token, err := s.auth.Login(r.Context(), r.FormValue("email"), r.FormValue("password"))
	if err != nil {
		s.render(w, "login.html", map[string]any{"Title": "Connexion", "Error": "Identifiants invalides"})
		return
	}
	s.setSessionCookie(w, token)
	http.Redirect(w, r, "/projects", http.StatusSeeOther)
}

func (s *Server) handleRegister(w http.ResponseWriter, r *http.Request) {
	_ = r.ParseForm()
	_, _, token, err := s.auth.Register(r.Context(),
		r.FormValue("email"), r.FormValue("password"), r.FormValue("name"), r.FormValue("org_name"),
	)
	if err != nil {
		s.render(w, "register.html", map[string]any{"Title": "Inscription", "Error": err.Error()})
		return
	}
	s.setSessionCookie(w, token)
	http.Redirect(w, r, "/projects", http.StatusSeeOther)
}

func (s *Server) handleLogout(w http.ResponseWriter, r *http.Request) {
	if c, err := r.Cookie("aai_session"); err == nil {
		_ = s.auth.Logout(r.Context(), c.Value)
	}
	http.SetCookie(w, &http.Cookie{Name: "aai_session", Value: "", Path: "/", MaxAge: -1})
	http.Redirect(w, r, "/", http.StatusSeeOther)
}

func (s *Server) handleProjectsPage(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	list, err := s.projects.List(r.Context(), p.Org.ID)
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	s.render(w, "projects.html", map[string]any{
		"Title": "Projets", "User": p.User, "Org": p.Org, "Projects": list, "Nav": "projects",
	})
}

func (s *Server) handleCreateProjectForm(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	if !p.Role.CanEdit() {
		http.Error(w, "forbidden", http.StatusForbidden)
		return
	}
	_ = r.ParseForm()
	proj, err := s.projects.Create(r.Context(), p.Org.ID, p.User.ID, r.FormValue("name"), r.FormValue("brief"))
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	http.Redirect(w, r, "/projects/"+proj.ID.String(), http.StatusSeeOther)
}

func (s *Server) handleProjectPage(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	id, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		http.NotFound(w, r)
		return
	}
	proj, err := s.projects.Get(r.Context(), p.Org.ID, id)
	if err != nil {
		http.NotFound(w, r)
		return
	}
	var rev any
	var compliance *plan.Report
	hasPreview := false
	planJSON := "{}"
	if proj.CurrentRevisionID != nil {
		if rrev, err := s.projects.GetRevision(r.Context(), *proj.CurrentRevisionID); err == nil {
			rev = rrev
			hasPreview = rrev.PreviewKey != ""
			if len(rrev.PlanDocument) > 0 {
				planJSON = string(rrev.PlanDocument)
			}
			if len(rrev.Compliance) > 0 {
				var report plan.Report
				if json.Unmarshal(rrev.Compliance, &report) == nil {
					compliance = &report
				}
			}
		}
	}
	s.render(w, "project.html", map[string]any{
		"Title": proj.Name, "User": p.User, "Org": p.Org, "Project": proj, "Revision": rev, "Role": p.Role,
		"HasPreview": hasPreview, "PlanJSON": template.JS(planJSON), "Compliance": compliance, "Nav": "plan2d",
	})
}

// handleProject3DPage affiche la page maquette 3D du projet (viewer + exports).
func (s *Server) handleProject3DPage(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	id, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		http.NotFound(w, r)
		return
	}
	proj, err := s.projects.Get(r.Context(), p.Org.ID, id)
	if err != nil {
		http.NotFound(w, r)
		return
	}
	var rev any
	if proj.CurrentRevisionID != nil {
		if rrev, err := s.projects.GetRevision(r.Context(), *proj.CurrentRevisionID); err == nil {
			rev = rrev
		}
	}
	s.render(w, "project3d.html", map[string]any{
		"Title": proj.Name + " — 3D", "User": p.User, "Org": p.Org, "Project": proj, "Revision": rev,
		"Nav": "plan3d",
	})
}

func (s *Server) handleEditorPage(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	id, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		http.NotFound(w, r)
		return
	}
	proj, err := s.projects.Get(r.Context(), p.Org.ID, id)
	if err != nil {
		http.NotFound(w, r)
		return
	}
	var planJSON string = `{"version":"1.0","units":"m","floor":{"level":0,"height_m":2.7,"bounds":{"width":12,"depth":10}},"walls":[],"rooms":[],"openings":[]}`
	var revisionID string
	if proj.CurrentRevisionID != nil {
		rev, err := s.projects.GetRevision(r.Context(), *proj.CurrentRevisionID)
		if err == nil {
			planJSON = string(rev.PlanDocument)
			revisionID = rev.ID.String()
		}
	}
	s.render(w, "editor.html", map[string]any{
		"Title": "Éditeur", "User": p.User, "Org": p.Org, "Project": proj,
		"PlanJSON": template.JS(planJSON), "RevisionID": revisionID, "CanEdit": p.Role.CanEdit(),
		"Nav": "editor",
	})
}

func (s *Server) handleViewer3DPage(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	id, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		http.NotFound(w, r)
		return
	}
	proj, err := s.projects.Get(r.Context(), p.Org.ID, id)
	if err != nil {
		http.NotFound(w, r)
		return
	}
	s.render(w, "viewer3d.html", map[string]any{
		"Title": "Maquette 3D", "User": p.User, "Org": p.Org, "Project": proj, "Nav": "plan3d",
	})
}

func (s *Server) handleBillingPage(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	if plan := r.URL.Query().Get("stub_checkout"); plan != "" && p.Role.CanBilling() {
		_ = s.billing.SetPlan(r.Context(), p.Org.ID, plan)
	}
	sub, _ := s.billing.GetSubscription(r.Context(), p.Org.ID)
	usage, _ := s.billing.Usage(r.Context(), p.Org.ID)
	limits := domain.LimitsForPlan(sub.Plan)
	s.render(w, "billing.html", map[string]any{
		"Title": "Abonnement", "User": p.User, "Org": p.Org,
		"Sub": sub, "Usage": usage, "Limits": limits,
		"StripeEnabled": s.billing.StripeEnabled(),
		"CanBilling":    p.Role.CanBilling(),
		"ErrQuota":      billing.ErrQuotaExceeded.Error(),
		"Nav":           "billing",
	})
}
