package jobs

import (
	"regexp"
	"strings"
	"unicode"
)

// Brand is the user-facing name of the generation engine. Vendor APIs and
// model identifiers stay internal: they must not appear in the product UI
// or in errors returned to end users.
const Brand = "Congo Architecture IA"

var publicFailure = "Le moteur " + Brand + " n’a pas pu terminer cette étape. Réessayez dans un instant."

// vendorNames matches third-party APIs, model ids and stack pieces that
// would leak the implementation if shown to a customer.
var vendorNames = regexp.MustCompile(`(?i)` + strings.Join([]string{
	`together(\s*ai)?`,
	`eden(\s*ai)?`,
	`edenai`,
	`gemini([-\s]?\d)?([-\s]?pro)?([-\s]?image)?([-\s]?preview)?`,
	`flux(\.2)?([-\s]?max)?`,
	`gpt-oss([-\s]?120b)?`,
	`openai`,
	`black-forest-labs`,
	`house[-_]?diffusion`,
	`controlnet`,
	`minio`,
	`blender`,
	`universal-ai`,
	`fastapi`,
}, `|`))

// PublicError rewrites a job/pipeline error for the product surface (JSON
// API, SSE). Internal strings (vendor names, stack traces, upstream JSON)
// become a generic branded message; already-safe user copy is left intact.
func PublicError(msg string) string {
	msg = strings.TrimSpace(msg)
	if msg == "" {
		return ""
	}
	if vendorNames.MatchString(msg) || looksInternal(msg) {
		return publicFailure
	}
	return msg
}

func looksInternal(msg string) bool {
	trimmed := strings.TrimSpace(msg)
	if trimmed == "" {
		return false
	}
	switch trimmed[0] {
	case '{', '[', '<':
		return true
	}
	lower := strings.ToLower(trimmed)
	for _, needle := range []string{
		"traceback",
		`"detail"`,
		"ai pipeline",
		"ai edit",
		"ai devis",
		"ai adapt",
		"httpx",
		"statuscode",
		"sqlstate",
		"pq:",
		"panic:",
	} {
		if strings.Contains(lower, needle) {
			return true
		}
	}
	// A dump of a Go/Python exception usually starts with a package path
	// or has no spaces at all (opaque token). Keep short French sentences.
	if strings.Contains(trimmed, "/") && strings.Contains(trimmed, ":") {
		return true
	}
	letters := 0
	for _, r := range trimmed {
		if unicode.IsLetter(r) {
			letters++
		}
	}
	return letters == 0
}

// PublicStep rewrites internal pipeline stage ids so the live UI never
// displays a vendor code (FLUX, Blender, …) even as a raw fallback.
func PublicStep(step string) string {
	switch strings.ToLower(strings.TrimSpace(step)) {
	case "flux", "flux2", "gemini", "eden":
		return "refine"
	case "blender":
		return "model"
	default:
		return step
	}
}
