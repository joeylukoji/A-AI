// Package admin serves the platform-administration views: read-only,
// cross-organisation listings of every plan generated on the instance.
//
// Every query here deliberately ignores org boundaries, which is the exact
// opposite of the rest of the application. Nothing in this package may be
// reachable without httpapi's requireAdmin check (users.is_platform_admin),
// and callers must never pass a value from here back into an org-scoped code
// path without re-checking ownership.
package admin

import (
	"context"
	"database/sql"
	"encoding/json"
	"time"

	plancalc "github.com/a-ai/a-ai/internal/plan"
	"github.com/google/uuid"
)

type Service struct {
	db *sql.DB
}

func NewService(db *sql.DB) *Service {
	return &Service{db: db}
}

// PlanRow is one generated plan as shown in the admin table, joined with the
// project, organisation and author it belongs to.
type PlanRow struct {
	RevisionID      uuid.UUID `json:"revision_id"`
	Version         int       `json:"version"`
	Source          string    `json:"source"`
	CreatedAt       time.Time `json:"created_at"`
	IsCurrent       bool      `json:"is_current"`
	HasPreview      bool      `json:"has_preview"`
	RoomCount       int       `json:"room_count"`
	ComplianceScore *int      `json:"compliance_score,omitempty"`
	ComplianceGrade string    `json:"compliance_grade,omitempty"`
	ProjectID       uuid.UUID `json:"project_id"`
	ProjectName     string    `json:"project_name"`
	OrgID           uuid.UUID `json:"org_id"`
	OrgName         string    `json:"org_name"`
	AuthorEmail     string    `json:"author_email"`
}

// Stats are the headline counters on the admin dashboard.
type Stats struct {
	Orgs         int `json:"orgs"`
	Users        int `json:"users"`
	Projects     int `json:"projects"`
	Plans        int `json:"plans"`
	PlansLast24h int `json:"plans_last_24h"`
	Jobs         int `json:"jobs"`
	FailedJobs   int `json:"failed_jobs"`
}

func (s *Service) Stats(ctx context.Context) (Stats, error) {
	var st Stats
	err := s.db.QueryRowContext(ctx, `
		SELECT (SELECT count(*) FROM orgs),
		       (SELECT count(*) FROM users),
		       (SELECT count(*) FROM projects),
		       (SELECT count(*) FROM plan_revisions),
		       (SELECT count(*) FROM plan_revisions WHERE created_at > now() - interval '24 hours'),
		       (SELECT count(*) FROM jobs),
		       (SELECT count(*) FROM jobs WHERE status='failed')
	`).Scan(&st.Orgs, &st.Users, &st.Projects, &st.Plans, &st.PlansLast24h, &st.Jobs, &st.FailedJobs)
	return st, err
}

// ListPlansFilter narrows the plan listing. Search matches the project name,
// organisation name or author email; empty means "no filter".
type ListPlansFilter struct {
	Search string
	Limit  int
	Offset int
}

const (
	defaultLimit = 50
	maxLimit     = 200
)

// ListPlans returns generated plans across every organisation, newest first,
// together with the total row count for pagination.
func (s *Service) ListPlans(ctx context.Context, f ListPlansFilter) (rows []PlanRow, total int, err error) {
	limit := f.Limit
	if limit <= 0 {
		limit = defaultLimit
	}
	if limit > maxLimit {
		limit = maxLimit
	}
	offset := f.Offset
	if offset < 0 {
		offset = 0
	}

	// The search term is passed as a bound parameter and only ever used inside
	// ILIKE, never concatenated into the SQL. '%' and '_' in user input act as
	// wildcards, which is acceptable for a search box.
	search := f.Search
	like := "%" + search + "%"
	matchAll := search == ""

	if err = s.db.QueryRowContext(ctx, `
		SELECT count(*)
		FROM plan_revisions r
		JOIN projects p ON p.id = r.project_id
		JOIN orgs o ON o.id = p.org_id
		LEFT JOIN users u ON u.id = r.created_by
		WHERE $1 OR p.name ILIKE $2 OR o.name ILIKE $2 OR COALESCE(u.email::text,'') ILIKE $2
	`, matchAll, like).Scan(&total); err != nil {
		return nil, 0, err
	}

	sqlRows, err := s.db.QueryContext(ctx, `
		SELECT r.id, r.version, r.source, r.created_at,
		       (p.current_revision_id = r.id) AS is_current,
		       COALESCE(r.preview_key,'') <> '' AS has_preview,
		       COALESCE(jsonb_array_length(r.plan_document->'rooms'), 0) AS room_count,
		       r.compliance,
		       p.id, p.name, o.id, o.name, COALESCE(u.email::text,'')
		FROM plan_revisions r
		JOIN projects p ON p.id = r.project_id
		JOIN orgs o ON o.id = p.org_id
		LEFT JOIN users u ON u.id = r.created_by
		WHERE $1 OR p.name ILIKE $2 OR o.name ILIKE $2 OR COALESCE(u.email::text,'') ILIKE $2
		ORDER BY r.created_at DESC
		LIMIT $3 OFFSET $4
	`, matchAll, like, limit, offset)
	if err != nil {
		return nil, 0, err
	}
	defer sqlRows.Close()

	rows = []PlanRow{}
	for sqlRows.Next() {
		var it PlanRow
		var comp []byte
		var isCurrent sql.NullBool
		if err := sqlRows.Scan(
			&it.RevisionID, &it.Version, &it.Source, &it.CreatedAt,
			&isCurrent, &it.HasPreview, &it.RoomCount, &comp,
			&it.ProjectID, &it.ProjectName, &it.OrgID, &it.OrgName, &it.AuthorEmail,
		); err != nil {
			return nil, 0, err
		}
		it.IsCurrent = isCurrent.Valid && isCurrent.Bool
		if len(comp) > 0 && string(comp) != "null" {
			var report plancalc.Report
			if json.Unmarshal(comp, &report) == nil && report.Total > 0 {
				score := report.Score
				it.ComplianceScore = &score
				it.ComplianceGrade = report.Grade
			}
		}
		rows = append(rows, it)
	}
	return rows, total, sqlRows.Err()
}

// OrgRow summarises one organisation for the admin dashboard.
type OrgRow struct {
	OrgID      uuid.UUID  `json:"org_id"`
	OrgName    string     `json:"org_name"`
	Plan       string     `json:"plan"`
	Members    int        `json:"members"`
	Projects   int        `json:"projects"`
	Plans      int        `json:"plans"`
	LastPlanAt *time.Time `json:"last_plan_at,omitempty"`
	CreatedAt  time.Time  `json:"created_at"`
}

// ListOrgs returns every organisation with its usage counters, busiest first.
func (s *Service) ListOrgs(ctx context.Context, limit int) ([]OrgRow, error) {
	if limit <= 0 || limit > maxLimit {
		limit = defaultLimit
	}
	rows, err := s.db.QueryContext(ctx, `
		SELECT o.id, o.name, COALESCE(sub.plan,'free'), o.created_at,
		       (SELECT count(*) FROM memberships m WHERE m.org_id = o.id),
		       (SELECT count(*) FROM projects p WHERE p.org_id = o.id),
		       (SELECT count(*) FROM plan_revisions r
		          JOIN projects p2 ON p2.id = r.project_id WHERE p2.org_id = o.id),
		       (SELECT max(r.created_at) FROM plan_revisions r
		          JOIN projects p3 ON p3.id = r.project_id WHERE p3.org_id = o.id)
		FROM orgs o
		LEFT JOIN subscriptions sub ON sub.org_id = o.id
		ORDER BY 7 DESC, o.created_at DESC
		LIMIT $1
	`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []OrgRow{}
	for rows.Next() {
		var it OrgRow
		var last sql.NullTime
		if err := rows.Scan(&it.OrgID, &it.OrgName, &it.Plan, &it.CreatedAt,
			&it.Members, &it.Projects, &it.Plans, &last); err != nil {
			return nil, err
		}
		if last.Valid {
			t := last.Time
			it.LastPlanAt = &t
		}
		out = append(out, it)
	}
	return out, rows.Err()
}

// PlanDetail is a single plan with its full document, for the admin detail view.
type PlanDetail struct {
	PlanRow
	PlanDocument json.RawMessage `json:"plan_document"`
	BuildingSpec json.RawMessage `json:"building_spec,omitempty"`
	PreviewKey   string          `json:"preview_key,omitempty"`
}

// GetPlan loads one plan by revision id, from any organisation.
func (s *Service) GetPlan(ctx context.Context, revisionID uuid.UUID) (*PlanDetail, error) {
	var it PlanDetail
	var comp []byte
	var isCurrent sql.NullBool
	err := s.db.QueryRowContext(ctx, `
		SELECT r.id, r.version, r.source, r.created_at,
		       (p.current_revision_id = r.id) AS is_current,
		       COALESCE(r.preview_key,'') <> '' AS has_preview,
		       COALESCE(jsonb_array_length(r.plan_document->'rooms'), 0) AS room_count,
		       r.compliance, p.id, p.name, o.id, o.name, COALESCE(u.email::text,''),
		       r.plan_document, r.building_spec, COALESCE(r.preview_key,'')
		FROM plan_revisions r
		JOIN projects p ON p.id = r.project_id
		JOIN orgs o ON o.id = p.org_id
		LEFT JOIN users u ON u.id = r.created_by
		WHERE r.id=$1
	`, revisionID).Scan(
		&it.RevisionID, &it.Version, &it.Source, &it.CreatedAt,
		&isCurrent, &it.HasPreview, &it.RoomCount, &comp,
		&it.ProjectID, &it.ProjectName, &it.OrgID, &it.OrgName, &it.AuthorEmail,
		&it.PlanDocument, &it.BuildingSpec, &it.PreviewKey,
	)
	if err != nil {
		return nil, err
	}
	it.IsCurrent = isCurrent.Valid && isCurrent.Bool
	if len(comp) > 0 && string(comp) != "null" {
		var report plancalc.Report
		if json.Unmarshal(comp, &report) == nil && report.Total > 0 {
			score := report.Score
			it.ComplianceScore = &score
			it.ComplianceGrade = report.Grade
		}
	}
	return &it, nil
}
