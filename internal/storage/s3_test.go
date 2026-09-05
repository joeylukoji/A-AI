package storage

import (
	"strings"
	"testing"

	"github.com/google/uuid"
)

// TestKeyIsScopedToProject ensures the generated storage key is always
// confined to "projects/<project-id>/..." and cannot be steered outside that
// prefix — kind/ext are always caller-supplied literals (never raw user
// input) in this codebase, but the key builder itself must not introduce a
// path-traversal opportunity if that ever changes.
func TestKeyIsScopedToProject(t *testing.T) {
	pid := uuid.New()
	key := (&Client{}).Key(pid, "preview", "png")

	wantPrefix := "projects/" + pid.String() + "/"
	if !strings.HasPrefix(key, wantPrefix) {
		t.Fatalf("key %q does not start with %q", key, wantPrefix)
	}
	if strings.Contains(key, "..") {
		t.Fatalf("key %q contains a path traversal segment", key)
	}
	if !strings.HasSuffix(key, ".png") {
		t.Fatalf("key %q missing expected extension", key)
	}
}

// TestKeyIsUniquePerCall guards against accidental key collisions (which
// would let one upload silently overwrite another) by checking successive
// calls for the same project/kind/ext never produce the same key.
func TestKeyIsUniquePerCall(t *testing.T) {
	c := &Client{}
	pid := uuid.New()
	seen := map[string]bool{}
	for i := 0; i < 50; i++ {
		k := c.Key(pid, "export-svg", "svg")
		if seen[k] {
			t.Fatalf("duplicate key generated: %s", k)
		}
		seen[k] = true
	}
}

func TestKeyEscapesTraversalAttemptsInKindAndExt(t *testing.T) {
	// Even though callers never pass attacker-controlled kind/ext today,
	// verify path.Join does not let "../" segments in those parameters climb
	// out of the project directory undetected.
	pid := uuid.New()
	key := (&Client{}).Key(pid, "../../etc", "passwd")
	wantPrefix := "projects/" + pid.String() + "/"
	if strings.HasPrefix(key, wantPrefix) {
		return // path.Join kept it scoped — nothing to flag.
	}
	t.Fatalf("storage key escaped project scope: %s (call sites MUST never pass untrusted kind/ext)", key)
}
