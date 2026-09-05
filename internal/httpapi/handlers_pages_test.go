package httpapi

import (
	"bytes"
	"encoding/json"
	"io"
	"log/slog"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/a-ai/a-ai/internal/domain"
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
			srv.render(rr, pg.name, pg.data)
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
