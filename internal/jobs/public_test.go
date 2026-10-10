package jobs

import "testing"

func TestPublicErrorHidesVendors(t *testing.T) {
	t.Parallel()
	cases := []string{
		`ai pipeline: {"detail":"Together API rate limit"}`,
		"FLUX.2-max timed out",
		"Gemini 3 Pro image failed",
		"eden ai 429: quota",
		"gpt-oss-120b returned empty JSON",
		"blender build failed: RuntimeError",
		"MinIO GetObject: NoSuchKey",
		`{"detail":"internal"}`,
		"traceback (most recent call last)",
	}
	for _, in := range cases {
		got := PublicError(in)
		if got != publicFailure {
			t.Errorf("PublicError(%q) = %q, want branded fallback", in, got)
		}
		if vendorNames.MatchString(got) {
			t.Errorf("sanitized error still names a vendor: %q", got)
		}
	}
}

func TestPublicErrorKeepsSafeCopy(t *testing.T) {
	t.Parallel()
	keep := []string{
		"générez un plan avant de le modifier",
		"pdf invalide",
		"indiquez la modification souhaitée",
	}
	for _, in := range keep {
		if got := PublicError(in); got != in {
			t.Errorf("PublicError(%q) = %q, want unchanged", in, got)
		}
	}
	if PublicError("") != "" {
		t.Fatal("empty error must stay empty")
	}
	if PublicError("   ") != "" {
		t.Fatal("blank error must stay empty")
	}
}

func TestPublicStepHidesVendorCodes(t *testing.T) {
	t.Parallel()
	if PublicStep("flux") != "refine" {
		t.Fatalf("flux step must not stay a vendor code, got %q", PublicStep("flux"))
	}
	if PublicStep("blender") != "model" {
		t.Fatalf("blender step must not stay a vendor code, got %q", PublicStep("blender"))
	}
	if PublicStep("nlu") != "nlu" {
		t.Fatalf("nlu step should stay, got %q", PublicStep("nlu"))
	}
}
