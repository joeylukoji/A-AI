package auth

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"errors"
	"fmt"
	"regexp"
	"strings"
	"time"

	"github.com/a-ai/a-ai/internal/domain"
	"github.com/google/uuid"
	"golang.org/x/crypto/bcrypt"
)

var (
	ErrInvalidCredentials = errors.New("invalid credentials")
	ErrEmailTaken         = errors.New("email already registered")
	ErrUnauthorized       = errors.New("unauthorized")
	// ErrReservedEmail is returned when signup targets an address configured as
	// a platform administrator: such accounts must not be self-registered.
	ErrReservedEmail = errors.New("email reserved for a platform administrator")
)

type Service struct {
	db *sql.DB
	// adminEmails mirrors ADMIN_EMAILS. Authenticate treats it as an override
	// on top of users.is_platform_admin so a newly registered administrator
	// gets access immediately: the boot-time DB sync only covers accounts that
	// already existed when the process started.
	adminEmails map[string]bool
}

func NewService(db *sql.DB, adminEmails []string) *Service {
	set := make(map[string]bool, len(adminEmails))
	for _, e := range adminEmails {
		if e = strings.ToLower(strings.TrimSpace(e)); e != "" {
			set[e] = true
		}
	}
	return &Service{db: db, adminEmails: set}
}

// IsConfiguredAdmin reports whether an email is listed in ADMIN_EMAILS.
func (s *Service) IsConfiguredAdmin(email string) bool {
	return s.adminEmails[strings.ToLower(strings.TrimSpace(email))]
}

type Session struct {
	ID        uuid.UUID
	UserID    uuid.UUID
	OrgID     *uuid.UUID
	Token     string
	ExpiresAt time.Time
}

func (s *Service) Register(ctx context.Context, email, password, name, orgName string) (*domain.User, *domain.Org, string, error) {
	email = strings.TrimSpace(strings.ToLower(email))
	if email == "" || len(password) < 8 || strings.TrimSpace(name) == "" {
		return nil, nil, "", fmt.Errorf("invalid registration payload")
	}
	// An address listed in ADMIN_EMAILS grants cross-organisation access at the
	// next boot. Self-service signup is unverified, so letting anyone claim
	// such an address would hand them every tenant's plans. The administrator
	// account must exist *before* its address is added to ADMIN_EMAILS.
	if s.IsConfiguredAdmin(email) {
		return nil, nil, "", ErrReservedEmail
	}
	hash, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		return nil, nil, "", err
	}
	if orgName == "" {
		orgName = name + " Studio"
	}
	slug := slugify(orgName)

	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return nil, nil, "", err
	}
	defer func() { _ = tx.Rollback() }()

	var userID uuid.UUID
	err = tx.QueryRowContext(ctx, `
		INSERT INTO users (email, password_hash, name)
		VALUES ($1,$2,$3) RETURNING id
	`, email, string(hash), name).Scan(&userID)
	if err != nil {
		if strings.Contains(err.Error(), "unique") {
			return nil, nil, "", ErrEmailTaken
		}
		return nil, nil, "", err
	}

	var orgID uuid.UUID
	err = tx.QueryRowContext(ctx, `
		INSERT INTO orgs (name, slug) VALUES ($1,$2) RETURNING id
	`, orgName, slug).Scan(&orgID)
	if err != nil {
		return nil, nil, "", err
	}

	if _, err = tx.ExecContext(ctx, `
		INSERT INTO memberships (org_id, user_id, role) VALUES ($1,$2,'owner')
	`, orgID, userID); err != nil {
		return nil, nil, "", err
	}
	if _, err = tx.ExecContext(ctx, `
		INSERT INTO subscriptions (org_id, plan, status) VALUES ($1,'free','active')
	`, orgID); err != nil {
		return nil, nil, "", err
	}

	token, err := s.createSessionTx(ctx, tx, userID, &orgID)
	if err != nil {
		return nil, nil, "", err
	}
	if err = tx.Commit(); err != nil {
		return nil, nil, "", err
	}

	return &domain.User{ID: userID, Email: email, Name: name},
		&domain.Org{ID: orgID, Name: orgName, Slug: slug},
		token, nil
}

func (s *Service) Login(ctx context.Context, email, password string) (string, error) {
	email = strings.TrimSpace(strings.ToLower(email))
	var user domain.User
	err := s.db.QueryRowContext(ctx, `
		SELECT id, email, password_hash, name FROM users WHERE email=$1
	`, email).Scan(&user.ID, &user.Email, &user.PasswordHash, &user.Name)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return "", ErrInvalidCredentials
		}
		return "", err
	}
	if bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(password)) != nil {
		return "", ErrInvalidCredentials
	}
	var orgID uuid.UUID
	err = s.db.QueryRowContext(ctx, `
		SELECT org_id FROM memberships WHERE user_id=$1 ORDER BY role='owner' DESC LIMIT 1
	`, user.ID).Scan(&orgID)
	if err != nil {
		return "", err
	}
	return s.CreateSession(ctx, user.ID, &orgID)
}

func (s *Service) CreateSession(ctx context.Context, userID uuid.UUID, orgID *uuid.UUID) (string, error) {
	return s.createSessionTx(ctx, s.db, userID, orgID)
}

type dbTX interface {
	ExecContext(context.Context, string, ...any) (sql.Result, error)
}

func (s *Service) createSessionTx(ctx context.Context, db dbTX, userID uuid.UUID, orgID *uuid.UUID) (string, error) {
	raw := make([]byte, 32)
	if _, err := rand.Read(raw); err != nil {
		return "", err
	}
	token := hex.EncodeToString(raw)
	sum := sha256.Sum256([]byte(token))
	tokenHash := hex.EncodeToString(sum[:])
	expires := time.Now().Add(30 * 24 * time.Hour)
	_, err := db.ExecContext(ctx, `
		INSERT INTO sessions (user_id, org_id, token_hash, expires_at)
		VALUES ($1,$2,$3,$4)
	`, userID, orgID, tokenHash, expires)
	return token, err
}

func (s *Service) Logout(ctx context.Context, token string) error {
	sum := sha256.Sum256([]byte(token))
	_, err := s.db.ExecContext(ctx, `DELETE FROM sessions WHERE token_hash=$1`, hex.EncodeToString(sum[:]))
	return err
}

type Principal struct {
	User domain.User
	Org  domain.Org
	Role domain.Role
	// IsPlatformAdmin is the cross-org administrator flag (users.is_platform_admin),
	// granted from ADMIN_EMAILS at boot. It is unrelated to Role, which only
	// carries rights inside the current org.
	IsPlatformAdmin bool
}

func (s *Service) Authenticate(ctx context.Context, token string) (*Principal, error) {
	if token == "" {
		return nil, ErrUnauthorized
	}
	sum := sha256.Sum256([]byte(token))
	var p Principal
	var orgID uuid.UUID
	err := s.db.QueryRowContext(ctx, `
		SELECT u.id, u.email, u.name, o.id, o.name, o.slug, m.role, u.is_platform_admin
		FROM sessions s
		JOIN users u ON u.id = s.user_id
		JOIN orgs o ON o.id = s.org_id
		JOIN memberships m ON m.org_id = o.id AND m.user_id = u.id
		WHERE s.token_hash=$1 AND s.expires_at > now()
	`, hex.EncodeToString(sum[:])).Scan(
		&p.User.ID, &p.User.Email, &p.User.Name,
		&orgID, &p.Org.Name, &p.Org.Slug, &p.Role, &p.IsPlatformAdmin,
	)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, ErrUnauthorized
		}
		return nil, err
	}
	p.Org.ID = orgID
	// Deliberately NOT promoting here from ADMIN_EMAILS. Doing so used to make
	// a newly registered administrator effective without a restart, but since
	// registration is self-service and unverified, it also meant anyone who
	// signed up with a configured address was instantly granted read access to
	// every organisation's plans. Promotion now happens only through
	// store.GrantPlatformAdmins at boot, against accounts that already exist,
	// and Register refuses to create an account for a configured address.
	return &p, nil
}

func (s *Service) SwitchOrg(ctx context.Context, token string, orgID uuid.UUID) error {
	p, err := s.Authenticate(ctx, token)
	if err != nil {
		return err
	}
	var role string
	err = s.db.QueryRowContext(ctx, `
		SELECT role FROM memberships WHERE org_id=$1 AND user_id=$2
	`, orgID, p.User.ID).Scan(&role)
	if err != nil {
		return ErrUnauthorized
	}
	sum := sha256.Sum256([]byte(token))
	_, err = s.db.ExecContext(ctx, `
		UPDATE sessions SET org_id=$1 WHERE token_hash=$2
	`, orgID, hex.EncodeToString(sum[:]))
	return err
}

func (s *Service) EnsureDemoUser(ctx context.Context) error {
	var n int
	if err := s.db.QueryRowContext(ctx, `SELECT COUNT(*) FROM users`).Scan(&n); err != nil {
		return err
	}
	if n > 0 {
		return nil
	}
	_, _, _, err := s.Register(ctx, "demo@a-ai.local", "demo-demo-demo", "Demo", "Demo Studio")
	return err
}

var nonAlnum = regexp.MustCompile(`[^a-z0-9]+`)

func slugify(s string) string {
	s = strings.ToLower(strings.TrimSpace(s))
	s = nonAlnum.ReplaceAllString(s, "-")
	s = strings.Trim(s, "-")
	if s == "" {
		s = "org"
	}
	return fmt.Sprintf("%s-%s", s, uuid.NewString()[:8])
}
