package auth

import (
	"strings"
	"testing"
)

func TestSlugify(t *testing.T) {
	got := slugify("Ada Studio")
	if !strings.HasPrefix(got, "ada-studio-") {
		t.Fatalf("got %q", got)
	}
	got = slugify("")
	if !strings.HasPrefix(got, "org-") {
		t.Fatalf("empty -> %q", got)
	}
}

func TestSlugifyUniqueSuffix(t *testing.T) {
	a := slugify("Same")
	b := slugify("Same")
	if a == b {
		t.Fatal("expected unique suffixes")
	}
}
