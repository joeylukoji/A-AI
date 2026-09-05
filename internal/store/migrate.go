package store

import (
	"context"
	"fmt"
	"strings"
)

const schema = `
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "citext";

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email CITEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS orgs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS memberships (
  org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('owner','architect','viewer')),
  PRIMARY KEY (org_id, user_id)
);

CREATE TABLE IF NOT EXISTS sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  org_id UUID REFERENCES orgs(id) ON DELETE SET NULL,
  token_hash TEXT UNIQUE NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS subscriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID UNIQUE NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  plan TEXT NOT NULL CHECK (plan IN ('free','pro','bureau')) DEFAULT 'free',
  stripe_customer_id TEXT,
  stripe_subscription_id TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  current_period_end TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS usage_quotas (
  org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  period_start DATE NOT NULL,
  generations_used INT NOT NULL DEFAULT 0,
  exports_used INT NOT NULL DEFAULT 0,
  gpu_minutes_used NUMERIC NOT NULL DEFAULT 0,
  PRIMARY KEY (org_id, period_start)
);

CREATE TABLE IF NOT EXISTS projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  brief TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'draft',
  current_revision_id UUID,
  created_by UUID NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS plan_revisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  version INT NOT NULL,
  source TEXT NOT NULL CHECK (source IN ('ai','editor','import')),
  plan_document JSONB NOT NULL,
  building_spec JSONB,
  compliance JSONB,
  preview_key TEXT,
  created_by UUID NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (project_id, version)
);

CREATE TABLE IF NOT EXISTS jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  input JSONB NOT NULL DEFAULT '{}',
  output JSONB NOT NULL DEFAULT '{}',
  error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS artifacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  revision_id UUID REFERENCES plan_revisions(id) ON DELETE SET NULL,
  job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
  kind TEXT NOT NULL,
  storage_key TEXT NOT NULL,
  content_type TEXT NOT NULL,
  checksum_sha256 TEXT,
  bytes BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memberships_user ON memberships(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_org ON projects(org_id);
CREATE INDEX IF NOT EXISTS idx_revisions_project ON plan_revisions(project_id);
CREATE INDEX IF NOT EXISTS idx_jobs_project ON jobs(project_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash);
`

func (d *DB) Migrate(ctx context.Context) error {
	if _, err := d.SQL.ExecContext(ctx, schema); err != nil {
		return fmt.Errorf("migrate: %w", err)
	}
	if _, err := d.SQL.ExecContext(ctx, `
		ALTER TABLE plan_revisions ADD COLUMN IF NOT EXISTS compliance JSONB;
	`); err != nil {
		return fmt.Errorf("migrate compliance: %w", err)
	}
	// Platform administrator flag: distinct from the per-org membership role
	// (owner/architect/viewer), which only grants rights inside one org. A
	// platform admin can see every org's plans from /admin.
	if _, err := d.SQL.ExecContext(ctx, `
		ALTER TABLE users ADD COLUMN IF NOT EXISTS is_platform_admin BOOLEAN NOT NULL DEFAULT false;
	`); err != nil {
		return fmt.Errorf("migrate is_platform_admin: %w", err)
	}
	return nil
}

// GrantPlatformAdmins flags the given emails as platform administrators and
// revokes the flag from everyone else, so ADMIN_EMAILS stays the single
// source of truth: removing an address from the env var actually removes the
// access on the next boot. Called at startup with the parsed ADMIN_EMAILS.
// With an empty list it revokes every admin (fail closed rather than leaving
// a forgotten admin behind).
func (d *DB) GrantPlatformAdmins(ctx context.Context, emails []string) error {
	if len(emails) == 0 {
		_, err := d.SQL.ExecContext(ctx,
			`UPDATE users SET is_platform_admin=false WHERE is_platform_admin`)
		if err != nil {
			return fmt.Errorf("revoke platform admins: %w", err)
		}
		return nil
	}
	// Passed as one comma-separated string and split server-side rather than
	// bound as a text[]: array binding depends on driver-specific handling of
	// []string, string_to_array works the same everywhere. Emails are
	// lowercased on both sides so the match is case-insensitive regardless of
	// the column type.
	lowered := make([]string, 0, len(emails))
	for _, e := range emails {
		e = strings.ToLower(strings.TrimSpace(e))
		if e != "" {
			lowered = append(lowered, e)
		}
	}
	if len(lowered) == 0 {
		return d.GrantPlatformAdmins(ctx, nil)
	}
	if _, err := d.SQL.ExecContext(ctx, `
		UPDATE users
		SET is_platform_admin = (lower(email::text) = ANY(string_to_array($1, ',')))
		WHERE is_platform_admin <> (lower(email::text) = ANY(string_to_array($1, ',')))
	`, strings.Join(lowered, ",")); err != nil {
		return fmt.Errorf("grant platform admins: %w", err)
	}
	return nil
}
