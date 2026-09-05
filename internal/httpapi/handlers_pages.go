package httpapi

import (
	"bytes"
	"encoding/json"
	"errors"
	"html/template"
	"net/http"

	"github.com/a-ai/a-ai/internal/auth"
	"github.com/a-ai/a-ai/internal/billing"
	"github.com/a-ai/a-ai/internal/domain"
	"github.com/a-ai/a-ai/internal/plan"
	"github.com/google/uuid"
)

// safeScriptJSON marks raw JSON as safe to inline verbatim inside a
// <script type="application/json">...</script> block, after neutralizing the
// byte sequences that could otherwise break out of it: "<", ">", "&",
// U+2028 and U+2029 are rewritten to their \uXXXX escapes — the exact
// transform encoding/json applies by default when marshaling, done here
// explicitly because raw is not produced by json.Marshal.
//
// This matters because raw is untrusted: it is the client-submitted
// plan_document (PUT /api/v1/projects/{id}/plan → handleSavePlan) stored
// verbatim as json.RawMessage and later rendered back into project.html and
// editor.html. Without this escaping, any org member able to edit a plan
// could store a room/name field containing e.g. `</script><script>...` and
// run arbitrary JS in the browser of every teammate (including owners) who
// opens the project — a stored XSS with privilege escalation. Passing the
// value through html/template's normal auto-escaping is not an option either:
// the whole point of the <script type="application/json"> block is that the
// browser must see the *unescaped* JSON, only shielded from the surrounding
// HTML/script parsing.
func safeScriptJSON(raw string) template.JS {
	var buf bytes.Buffer
	json.HTMLEscape(&buf, []byte(raw))
	return template.JS(buf.String())
}

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

// maxFormBodyBytes caps HTML form submissions for the same reason
// maxJSONBodyBytes caps JSON bodies: r.ParseForm reads the whole body into
// memory with no size limit of its own.
const maxFormBodyBytes = 1 << 20 // 1 MiB

func (s *Server) handleLogin(w http.ResponseWriter, r *http.Request) {
	r.Body = http.MaxBytesReader(w, r.Body, maxFormBodyBytes)
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
	r.Body = http.MaxBytesReader(w, r.Body, maxFormBodyBytes)
	_ = r.ParseForm()
	_, _, token, err := s.auth.Register(r.Context(),
		r.FormValue("email"), r.FormValue("password"), r.FormValue("name"), r.FormValue("org_name"),
	)
	if err != nil {
		// auth.Register can also surface raw DB errors (e.g. on the org/
		// membership inserts) — never show those to the client; only the
		// known, safe sentinel gets its own message.
		msg := "Inscription impossible, réessayez."
		switch {
		case errors.Is(err, auth.ErrEmailTaken):
			msg = "Cet email est déjà utilisé."
		case err.Error() == "invalid registration payload":
			msg = "Merci de renseigner un email, un nom et un mot de passe d’au moins 8 caractères."
		default:
			s.log.Error("register failed", "err", err)
		}
		s.render(w, "register.html", map[string]any{"Title": "Inscription", "Error": msg})
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
		s.log.Error("list projects failed", "org_id", p.Org.ID, "err", err)
		http.Error(w, "internal server error", http.StatusInternalServerError)
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
	r.Body = http.MaxBytesReader(w, r.Body, maxFormBodyBytes)
	_ = r.ParseForm()
	proj, err := s.projects.Create(r.Context(), p.Org.ID, p.User.ID, r.FormValue("name"), r.FormValue("brief"))
	if err != nil {
		s.log.Error("create project failed", "org_id", p.Org.ID, "err", err)
		http.Error(w, "internal server error", http.StatusInternalServerError)
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
		"HasPreview": hasPreview, "PlanJSON": safeScriptJSON(planJSON), "Compliance": compliance, "Nav": "plan2d",
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
		"PlanJSON": safeScriptJSON(planJSON), "RevisionID": revisionID, "CanEdit": p.Role.CanEdit(),
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
