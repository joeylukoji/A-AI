package auth

import (
	"context"
	"errors"
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

// TestIsConfiguredAdminNormalisesEmails covers the ADMIN_EMAILS override that
// makes a platform administrator effective immediately: the boot-time DB sync
// only flags accounts that already exist, so an admin who registers after the
// process started would otherwise be locked out of /admin until a restart.
func TestIsConfiguredAdminNormalisesEmails(t *testing.T) {
	svc := NewService(nil, []string{" Boss@Example.COM ", "", "second@example.com"})

	for _, email := range []string{"boss@example.com", "BOSS@EXAMPLE.COM", " boss@example.com "} {
		if !svc.IsConfiguredAdmin(email) {
			t.Errorf("%q should be recognised as a configured admin", email)
		}
	}
	if !svc.IsConfiguredAdmin("second@example.com") {
		t.Error("second configured admin should be recognised")
	}
	for _, email := range []string{"someone@example.com", "", "boss@example.com.evil.tld"} {
		if svc.IsConfiguredAdmin(email) {
			t.Errorf("%q must NOT be treated as an admin", email)
		}
	}
}

// TestNoConfiguredAdminsWhenListEmpty is the fail-closed case: with
// ADMIN_EMAILS unset, no email may be considered an administrator.
func TestNoConfiguredAdminsWhenListEmpty(t *testing.T) {
	svc := NewService(nil, nil)
	if svc.IsConfiguredAdmin("anyone@example.com") {
		t.Fatal("no one should be an admin when ADMIN_EMAILS is empty")
	}
}

// TestRegisterRefusesConfiguredAdminEmail closes a privilege-escalation hole:
// an address listed in ADMIN_EMAILS is promoted to platform administrator at
// boot, and signup is self-service and unverified. If anyone could register
// such an address, they would be handed read access to every organisation's
// plans. The administrator account must therefore exist before its address is
// added to ADMIN_EMAILS.
func TestRegisterRefusesConfiguredAdminEmail(t *testing.T) {
	svc := NewService(nil, []string{"boss@example.com"})

	// nil *sql.DB would panic if we ever reached the database, so reaching the
	// sentinel also proves the check happens before any query.
	_, _, _, err := svc.Register(context.Background(), "BOSS@Example.com", "password123", "Squatter", "Org")
	if !errors.Is(err, ErrReservedEmail) {
		t.Fatalf("registering a configured admin address must be refused, got %v", err)
	}
}
