package httpapi

import (
	"bytes"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/a-ai/a-ai/internal/admin"
	"github.com/a-ai/a-ai/internal/config"
	"github.com/a-ai/a-ai/internal/domain"
	"github.com/a-ai/a-ai/internal/project"
	"github.com/a-ai/a-ai/web"
	"github.com/google/uuid"
)

// TestSafeScriptJSONNeutralizesScriptBreakout is the regression test for a
// stored-XSS-with-privilege-escalation bug: project.html and editor.html both
// embed the plan document verbatim inside
// <script type="application/json">{{.PlanJSON}}</script>, and PlanJSON used
// to be wrapped in raw template.JS (no escaping at all). Any org member able
// to save a plan (PUT /api/v1/projects/{id}/plan) could put
// `</script><script>...` in a text field (e.g. a room name) and run
// arbitrary JS in the browser of every teammate — including owners — who
// later opened the project or editor page.
func TestSafeScriptJSONNeutralizesScriptBreakout(t *testing.T) {
	payload := `{"rooms":[{"name":"</script><script>alert(document.cookie)</script>"}]}`
	out := string(safeScriptJSON(payload))

	if strings.Contains(out, "</script>") {
		t.Fatalf("safeScriptJSON left a live closing </script> tag: %s", out)
	}
	if strings.Contains(out, "<script>") {
		t.Fatalf("safeScriptJSON left a live opening <script> tag: %s", out)
	}
	if !strings.Contains(out, `\u003c/script\u003e`) {
		t.Fatalf("expected the closing tag escaped as \\u003c/script\\u003e, got: %s", out)
	}

	// The content must still be recoverable JSON once a browser's JSON.parse
	// decodes the \uXXXX escapes — i.e. we changed representation, not data.
	restored := strings.NewReplacer(`\u003c`, "<", `\u003e`, ">", `\u0026`, "&").Replace(out)
	var v any
	if err := json.Unmarshal([]byte(restored), &v); err != nil {
		t.Fatalf("escaped JSON does not round-trip back to valid JSON: %v (%s)", err, out)
	}
}

// TestSafeScriptJSONEscapesLineSeparators guards the two other characters
// json.HTMLEscape neutralizes: U+2028/U+2029 are valid inside a JSON string
// but are illegal in a JS string literal / can terminate statements in some
// script contexts, so they must be escaped too.
func TestSafeScriptJSONEscapesLineSeparators(t *testing.T) {
	payload := "{\"a\":\"x\u2028y\u2029z\"}"
	out := string(safeScriptJSON(payload))
	if strings.ContainsRune(out, '\u2028') || strings.ContainsRune(out, '\u2029') {
		t.Fatalf("U+2028/U+2029 not escaped: %q", out)
	}
}

// TestProjectAndEditorPagesEscapeStoredXSSInPlanDocument renders the real
// project.html and editor.html templates with a plan document carrying the
// exact attacker payload and asserts it never surfaces as a live <script>
// tag in the resulting HTML.
func TestProjectAndEditorPagesEscapeStoredXSSInPlanDocument(t *testing.T) {
	tmpl, err := web.Templates()
	if err != nil {
		t.Fatal(err)
	}
	srv := &Server{tmpl: tmpl, log: slog.New(slog.NewTextHandler(io.Discard, nil))}

	const xssPayload = `</script><script>alert(document.cookie)</script>`
	marshaled, err := json.Marshal(map[string]any{
		"version": "1.0", "units": "m",
		"floor": map[string]any{"level": 0, "height_m": 2.7, "bounds": map[string]any{"width": 10, "depth": 8}},
		"walls": []any{}, "openings": []any{},
		"rooms": []any{map[string]any{"id": "r1", "name": xssPayload, "type": "living", "polygon": []any{}}},
	})
	if err != nil {
		t.Fatal(err)
	}
	// json.Marshal HTML-escapes by default; undo that to reproduce the actual
	// vulnerable input — plan_document is captured as json.RawMessage
	// straight off the PUT /plan request body, byte for byte, with no such
	// escaping applied.
	planDoc := []byte(strings.NewReplacer(`\u003c`, "<", `\u003e`, ">", `\u0026`, "&").Replace(string(marshaled)))
	if !bytes.Contains(planDoc, []byte(xssPayload)) {
		t.Fatalf("test setup: payload not present verbatim in plan document: %s", planDoc)
	}

	proj := &domain.Project{ID: uuid.New(), OrgID: uuid.New(), Name: "Test"}
	rev := &domain.PlanRevision{ID: uuid.New(), ProjectID: proj.ID, Version: 1, Source: "editor", PlanDocument: planDoc}
	user := domain.User{ID: uuid.New(), Name: "Ada", Email: "a@b.c"}
	org := domain.Org{ID: proj.OrgID, Name: "Studio"}

	pages := []struct {
		name string
		data map[string]any
	}{
		{"project.html", map[string]any{
			"Title": proj.Name, "User": user, "Org": org, "Project": proj, "Revision": rev, "Role": domain.RoleOwner,
			"HasPreview": false, "PlanJSON": safeScriptJSON(string(planDoc)), "Compliance": nil, "Nav": "plan2d",
		}},
		{"editor.html", map[string]any{
			"Title": "Éditeur", "User": user, "Org": org, "Project": proj,
			"PlanJSON": safeScriptJSON(string(planDoc)), "RevisionID": rev.ID.String(), "CanEdit": true,
			"Nav": "editor",
		}},
	}

	for _, pg := range pages {
		t.Run(pg.name, func(t *testing.T) {
			rr := httptest.NewRecorder()
			srv.render(rr, httptest.NewRequest(http.MethodGet, "/", nil), pg.name, pg.data)
			body := rr.Body.String()
			if rr.Code >= 400 {
				t.Fatalf("render failed: status %d body %s", rr.Code, body)
			}
			if strings.Contains(body, xssPayload) {
				t.Fatalf("%s: XSS payload present verbatim in rendered HTML (script breakout): %s", pg.name, body)
			}
			if !strings.Contains(body, `\u003c/script\u003e`) {
				t.Fatalf("%s: expected the escaped closing tag to survive inside the embedded JSON blob", pg.name)
			}
		})
	}
}

// renderedPageIsComplete fails when a template execution error truncated the
// output. render() streams straight to the ResponseWriter, so a mid-execution
// failure leaves a 200 with a half-written page plus the literal text
// "template error" — the status code alone never reveals it.
func renderedPageIsComplete(t *testing.T, name, body string) {
	t.Helper()
	if strings.Contains(body, "template error") {
		t.Fatalf("%s: template execution failed, page truncated. Tail: %q",
			name, body[max(0, len(body)-300):])
	}
	if !strings.HasSuffix(strings.TrimSpace(body), "</html>") {
		t.Fatalf("%s: page does not reach </html>, output was truncated. Tail: %q",
			name, body[max(0, len(body)-300):])
	}
}

// TestPagesWithComplianceScoreRenderCompletely is the regression test for a
// bug that broke every page showing a compliance badge: the score is a *int
// and the badge colour was chosen with `{{if ge .ComplianceScore 80}}`.
// html/template's ge/lt reject a pointer ("invalid type for comparison"), so
// as soon as a plan had a compliance report — which every generated plan has —
// execution aborted mid-tag. The page still returned 200 with a truncated
// body: on project.html that cut off the whole history card and every script
// below it (generate, restore, export), i.e. exactly the feature the page was
// added for. The templates now compare the Score() accessor instead.
func TestPagesWithComplianceScoreRenderCompletely(t *testing.T) {
	tmpl, err := web.Templates()
	if err != nil {
		t.Fatal(err)
	}
	srv := &Server{tmpl: tmpl, log: slog.New(slog.NewTextHandler(io.Discard, nil))}

	user := domain.User{ID: uuid.New(), Name: "Ada", Email: "a@b.c"}
	org := domain.Org{ID: uuid.New(), Name: "Studio"}
	proj := &domain.Project{ID: uuid.New(), OrgID: org.ID, Name: "Villa", Status: "ready"}

	// One score per badge branch (>=80, >=50, <50) so all three are executed.
	for _, score := range []int{92, 64, 12} {
		score := score
		t.Run(strconv.Itoa(score), func(t *testing.T) {
			scoredProject := *proj
			scoredProject.ComplianceScore = &score
			scoredProject.ComplianceGrade = "B"

			revisions := []project.RevisionSummary{{
				ID: uuid.New(), ProjectID: proj.ID, Version: 2, Source: "ai",
				ComplianceScore: &score, ComplianceGrade: "B", RoomCount: 4,
				CreatedAt: time.Now(), IsCurrent: true,
			}, {
				ID: uuid.New(), ProjectID: proj.ID, Version: 1, Source: "ai",
				RoomCount: 3, CreatedAt: time.Now().Add(-time.Hour),
			}}
			planRows := []admin.PlanRow{{
				RevisionID: uuid.New(), Version: 2, Source: "ai", CreatedAt: time.Now(),
				RoomCount: 4, ComplianceScore: &score, ComplianceGrade: "B",
				ProjectID: proj.ID, ProjectName: proj.Name,
				OrgID: org.ID, OrgName: org.Name, AuthorEmail: user.Email,
			}}

			pages := []struct {
				name string
				data map[string]any
			}{
				{"projects.html", map[string]any{
					"Title": "Projets", "User": user, "Org": org,
					"Projects": []domain.Project{scoredProject}, "Nav": "projects",
				}},
				{"project.html", map[string]any{
					"Title": proj.Name, "User": user, "Org": org, "Project": proj,
					"Revision": nil, "Role": domain.RoleOwner, "HasPreview": false,
					"PlanJSON": safeScriptJSON("{}"), "Compliance": nil, "Nav": "plan2d",
					"Revisions": revisions,
				}},
				{"admin.html", map[string]any{
					"Title": "Administration", "User": user, "Org": org, "Role": domain.RoleOwner,
					"Nav": "admin", "IsPlatformAdmin": true,
					"Stats":       admin.Stats{Orgs: 1, Users: 1, Projects: 1, Plans: 2},
					"Orgs":        []admin.OrgRow{{OrgID: org.ID, OrgName: org.Name, Plan: "free", Members: 1}},
					"RecentPlans": planRows,
				}},
				{"admin_plans.html", map[string]any{
					"Title": "Tous les plans", "User": user, "Org": org, "Role": domain.RoleOwner,
					"Nav": "admin", "IsPlatformAdmin": true,
					"Plans": planRows, "Total": 1, "Search": "",
					"Page": 1, "LastPage": 1, "PrevPage": 0, "NextPage": 2,
				}},
			}

			for _, pg := range pages {
				rr := httptest.NewRecorder()
				srv.render(rr, httptest.NewRequest(http.MethodGet, "/", nil), pg.name, pg.data)
				renderedPageIsComplete(t, pg.name, rr.Body.String())
				if !strings.Contains(rr.Body.String(), strconv.Itoa(score)+"/100") {
					t.Errorf("%s: compliance badge %d/100 missing from the page", pg.name, score)
				}
			}
		})
	}
}

// TestScoreAccessorsHandleNilPointer pins the contract the templates rely on:
// no compliance report means 0, never a panic.
func TestScoreAccessorsHandleNilPointer(t *testing.T) {
	if got := (domain.Project{}).Score(); got != 0 {
		t.Errorf("domain.Project.Score() with no report = %d, want 0", got)
	}
	if got := (project.RevisionSummary{}).Score(); got != 0 {
		t.Errorf("project.RevisionSummary.Score() with no report = %d, want 0", got)
	}
	if got := (admin.PlanRow{}).Score(); got != 0 {
		t.Errorf("admin.PlanRow.Score() with no report = %d, want 0", got)
	}
	n := 73
	if got := (admin.PlanRow{ComplianceScore: &n}).Score(); got != 73 {
		t.Errorf("admin.PlanRow.Score() = %d, want 73", got)
	}
}

// TestProductPagesHideVendorModels is the customer-facing copy contract:
// Together / FLUX / Gemini / gpt-oss / Blender must not appear in the UI.
func TestProductPagesHideVendorModels(t *testing.T) {
	tmpl, err := web.Templates()
	if err != nil {
		t.Fatal(err)
	}
	srv := &Server{tmpl: tmpl, log: slog.New(slog.NewTextHandler(io.Discard, nil))}
	user := domain.User{ID: uuid.New(), Name: "Ada", Email: "a@b.c"}
	org := domain.Org{ID: uuid.New(), Name: "Studio"}
	proj := &domain.Project{ID: uuid.New(), OrgID: org.ID, Name: "Villa", Status: "ready"}

	pages := []struct {
		name string
		data map[string]any
	}{
		{"landing.html", map[string]any{"Title": "Accueil"}},
		{"project.html", map[string]any{
			"Title": proj.Name, "User": user, "Org": org, "Project": proj,
			"Revision": nil, "Role": domain.RoleOwner, "HasPreview": false,
			"PlanJSON": safeScriptJSON("{}"), "Compliance": nil, "Nav": "plan2d",
			"Revisions": []project.RevisionSummary{},
		}},
		{"project3d.html", map[string]any{
			"Title": proj.Name, "User": user, "Org": org, "Project": proj,
			"Revision": nil, "Role": domain.RoleOwner, "Nav": "plan3d",
		}},
	}
	forbidden := []string{
		"Together", "FLUX", "Gemini", "gpt-oss", "Eden", "Blender", "MinIO",
		"QCAD", "LibreCAD", "HouseDiffusion",
	}
	for _, pg := range pages {
		rr := httptest.NewRecorder()
		srv.render(rr, httptest.NewRequest(http.MethodGet, "/", nil), pg.name, pg.data)
		body := rr.Body.String()
		for _, word := range forbidden {
			if strings.Contains(body, word) {
				t.Errorf("%s leaks vendor %q", pg.name, word)
			}
		}
		if !strings.Contains(body, "Congo Architecture") {
			t.Errorf("%s: expected Congo Architecture branding", pg.name)
		}
	}
}

// TestDashboardShellUsesLocalCSSAndScrollableMobileLayout guards two UX
// regressions: Tailwind Play CDN (slow first paint) and a 100dvh overflow-hidden
// shell that clipped project cards on phones.
func TestDashboardShellUsesLocalCSSAndScrollableMobileLayout(t *testing.T) {
	tmpl, err := web.Templates()
	if err != nil {
		t.Fatal(err)
	}
	srv := &Server{tmpl: tmpl, log: slog.New(slog.NewTextHandler(io.Discard, nil))}
	user := domain.User{ID: uuid.New(), Name: "Ada", Email: "a@b.c"}
	org := domain.Org{ID: uuid.New(), Name: "Studio"}
	proj := &domain.Project{ID: uuid.New(), OrgID: org.ID, Name: "Villa longue qui doit revenir à la ligne", Status: "ready"}

	pages := []struct {
		name string
		data map[string]any
	}{
		{"projects.html", map[string]any{
			"Title": "Projets", "User": user, "Org": org,
			"Projects": []domain.Project{*proj}, "Nav": "projects",
		}},
		{"project.html", map[string]any{
			"Title": proj.Name, "User": user, "Org": org, "Project": proj,
			"Revision": &domain.PlanRevision{ID: uuid.New(), ProjectID: proj.ID, Version: 1, Source: "ai"},
			"Role": domain.RoleOwner, "HasPreview": false,
			"PlanJSON": safeScriptJSON("{}"), "Compliance": nil, "Nav": "plan2d",
			"Revisions": []project.RevisionSummary{},
		}},
	}
	for _, pg := range pages {
		rr := httptest.NewRecorder()
		srv.render(rr, httptest.NewRequest(http.MethodGet, "/", nil), pg.name, pg.data)
		body := rr.Body.String()
		renderedPageIsComplete(t, pg.name, body)
		if strings.Contains(body, "cdn.tailwindcss.com") {
			t.Errorf("%s still loads Tailwind from the Play CDN", pg.name)
		}
		if !strings.Contains(body, "/static/css/tailwind.css") {
			t.Errorf("%s: expected compiled local Tailwind CSS", pg.name)
		}
		if !strings.Contains(body, "min-h-[100dvh]") {
			t.Errorf("%s: expected a min-height mobile shell so project cards are not clipped", pg.name)
		}
		if strings.Contains(body, "h-[100dvh] overflow-hidden flex flex-col md:flex-row") {
			t.Errorf("%s: 100dvh overflow-hidden shell clips cards on phones", pg.name)
		}
	}
}

// TestGeminiOnlyPausesEditorAnd3D: with GEMINI_ONLY the editor and 3D pages
// redirect to the project page, and the project page links to neither.
func TestGeminiOnlyPausesEditorAnd3D(t *testing.T) {
	tmpl, err := web.Templates()
	if err != nil {
		t.Fatal(err)
	}
	srv := &Server{tmpl: tmpl, log: slog.New(slog.NewTextHandler(io.Discard, nil)), cfg: config.Config{GeminiOnly: true}}
	id := uuid.New()

	for _, path := range []string{"/editor", "/3d", "/viewer3d"} {
		req := httptest.NewRequest(http.MethodGet, "/projects/"+id.String()+path, nil)
		req.SetPathValue("id", id.String())
		rr := httptest.NewRecorder()
		srv.pausedInGeminiOnly(func(http.ResponseWriter, *http.Request) { t.Errorf("%s handler ran", path) })(rr, req)
		if rr.Code != http.StatusSeeOther || rr.Header().Get("Location") != "/projects/"+id.String() {
			t.Errorf("%s: got %d %q, want redirect to project", path, rr.Code, rr.Header().Get("Location"))
		}
	}

	proj := &domain.Project{ID: id, Name: "Villa", Status: "ready"}
	rev := &domain.PlanRevision{ID: uuid.New(), ProjectID: id, Version: 1, PlanDocument: []byte("{}")}
	rr := httptest.NewRecorder()
	srv.render(rr, httptest.NewRequest(http.MethodGet, "/", nil), "project.html", map[string]any{
		"Title": "Villa", "User": domain.User{}, "Org": domain.Org{}, "Project": proj, "Revision": rev,
		"Role": domain.RoleOwner, "HasPreview": false, "PlanJSON": safeScriptJSON("{}"), "Nav": "plan2d",
		"Revisions": []project.RevisionSummary{},
	})
	body := rr.Body.String()
	for _, link := range []string{"/editor", "/3d"} {
		if strings.Contains(body, id.String()+link) {
			t.Errorf("project page still links to %s", link)
		}
	}
	if !strings.Contains(body, "Aperçu indisponible") || strings.Contains(body, `id="plan-thumb"`) {
		t.Error("without a preview the page must say it is unavailable, not draw the vector plan")
	}
}
