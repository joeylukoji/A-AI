package project

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/a-ai/a-ai/internal/domain"
	plancalc "github.com/a-ai/a-ai/internal/plan"
	"github.com/google/uuid"
)

var ErrNotFound = errors.New("project not found")
var ErrForbidden = errors.New("forbidden")
var ErrConflict = errors.New("revision conflict")

// RevisionSummary describes one saved plan without carrying its plan_document
// payload. The project page lists every revision ever generated, and those
// documents are large (hundreds of KB each on a big plan) — loading them all
// just to render "version 3, généré le ..." would be wasteful.
type RevisionSummary struct {
	ID              uuid.UUID `json:"id"`
	ProjectID       uuid.UUID `json:"project_id"`
	Version         int       `json:"version"`
	Source          string    `json:"source"`
	HasPreview      bool      `json:"has_preview"`
	IsCurrent       bool      `json:"is_current"`
	ComplianceScore *int      `json:"compliance_score,omitempty"`
	ComplianceGrade string    `json:"compliance_grade,omitempty"`
	RoomCount       int       `json:"room_count"`
	CreatedAt       time.Time `json:"created_at"`
	CreatedBy       uuid.UUID `json:"created_by"`
}

// Score returns the compliance score as a plain int, 0 when the revision has
// no compliance report. Templates need this: html/template's ge/lt refuse a
// *int ("invalid type for comparison") and the resulting execution error
// truncates the page mid-tag, so the history card must compare Score, never
// ComplianceScore. The pointer field stays for the JSON API, where the
// distinction between "no report" and "scored 0" is meaningful.
func (r RevisionSummary) Score() int {
	if r.ComplianceScore == nil {
		return 0
	}
	return *r.ComplianceScore
}

type Service struct {
	db *sql.DB
}

func NewService(db *sql.DB) *Service {
	return &Service{db: db}
}

func (s *Service) List(ctx context.Context, orgID uuid.UUID) ([]domain.Project, error) {
	rows, err := s.db.QueryContext(ctx, `
		SELECT p.id, p.org_id, p.name, p.brief, p.status, p.current_revision_id, p.created_by, p.created_at, p.updated_at,
		       r.plan_document, r.compliance
		FROM projects p
		LEFT JOIN plan_revisions r ON r.id = p.current_revision_id
		WHERE p.org_id=$1 ORDER BY p.updated_at DESC
	`, orgID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []domain.Project
	for rows.Next() {
		var p domain.Project
		var planDoc, comp []byte
		if err := rows.Scan(&p.ID, &p.OrgID, &p.Name, &p.Brief, &p.Status, &p.CurrentRevisionID, &p.CreatedBy, &p.CreatedAt, &p.UpdatedAt, &planDoc, &comp); err != nil {
			return nil, err
		}
		attachProjectScore(&p, planDoc, comp)
		out = append(out, p)
	}
	return out, rows.Err()
}

func (s *Service) Create(ctx context.Context, orgID, userID uuid.UUID, name, brief string) (*domain.Project, error) {
	if name == "" {
		name = "Nouveau projet"
	}
	var p domain.Project
	err := s.db.QueryRowContext(ctx, `
		INSERT INTO projects (org_id, name, brief, created_by)
		VALUES ($1,$2,$3,$4)
		RETURNING id, org_id, name, brief, status, current_revision_id, created_by, created_at, updated_at
	`, orgID, name, brief, userID).Scan(
		&p.ID, &p.OrgID, &p.Name, &p.Brief, &p.Status, &p.CurrentRevisionID, &p.CreatedBy, &p.CreatedAt, &p.UpdatedAt,
	)
	return &p, err
}

func (s *Service) Get(ctx context.Context, orgID, projectID uuid.UUID) (*domain.Project, error) {
	var p domain.Project
	err := s.db.QueryRowContext(ctx, `
		SELECT id, org_id, name, brief, status, current_revision_id, created_by, created_at, updated_at
		FROM projects WHERE id=$1 AND org_id=$2
	`, projectID, orgID).Scan(
		&p.ID, &p.OrgID, &p.Name, &p.Brief, &p.Status, &p.CurrentRevisionID, &p.CreatedBy, &p.CreatedAt, &p.UpdatedAt,
	)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	return &p, err
}

func (s *Service) UpdateBrief(ctx context.Context, orgID, projectID uuid.UUID, brief string) error {
	res, err := s.db.ExecContext(ctx, `
		UPDATE projects SET brief=$1, updated_at=now() WHERE id=$2 AND org_id=$3
	`, brief, projectID, orgID)
	if err != nil {
		return err
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return ErrNotFound
	}
	return nil
}

func (s *Service) SetStatus(ctx context.Context, projectID uuid.UUID, status string) error {
	_, err := s.db.ExecContext(ctx, `UPDATE projects SET status=$1, updated_at=now() WHERE id=$2`, status, projectID)
	return err
}

func (s *Service) LatestRevision(ctx context.Context, projectID uuid.UUID) (*domain.PlanRevision, error) {
	r, err := scanRevision(s.db.QueryRowContext(ctx, `
		SELECT `+revisionColumns+`
		FROM plan_revisions r WHERE r.project_id=$1 ORDER BY r.version DESC LIMIT 1
	`, projectID).Scan)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	return r, err
}

// GetRevision loads a revision by id with no ownership check. Only call this
// after the caller has already established (elsewhere) that the revision's
// project belongs to the right org/user — e.g. because it was reached via
// proj.CurrentRevisionID on an org-scoped project.Get. Handlers that accept a
// bare revision id from the client (URL path, request body) MUST use
// GetRevisionForOrg instead, or any authenticated user could read another
// org's revisions by guessing/enumerating UUIDs (IDOR).
func (s *Service) GetRevision(ctx context.Context, revisionID uuid.UUID) (*domain.PlanRevision, error) {
	r, err := scanRevision(s.db.QueryRowContext(ctx, `
		SELECT `+revisionColumns+`
		FROM plan_revisions r WHERE r.id=$1
	`, revisionID).Scan)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	return r, err
}

// GetRevisionForOrg loads a revision only when it belongs to a project owned
// by orgID. Use this (not GetRevision) whenever the revision id comes
// directly from an untrusted request rather than from an already org-scoped
// project lookup.
func (s *Service) GetRevisionForOrg(ctx context.Context, orgID, revisionID uuid.UUID) (*domain.PlanRevision, error) {
	r, err := scanRevision(s.db.QueryRowContext(ctx, `
		SELECT `+revisionColumns+`
		FROM plan_revisions r
		JOIN projects p ON p.id = r.project_id
		WHERE r.id=$1 AND p.org_id=$2
	`, revisionID, orgID).Scan)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	return r, err
}

// ListRevisionSummaries returns every plan ever generated for a project,
// newest first, without the plan_document/building_spec payloads. Callers must
// have already checked that the project belongs to the caller's org (as
// Service.Get does) — this takes a project id, not an org id.
func (s *Service) ListRevisionSummaries(ctx context.Context, projectID uuid.UUID) ([]RevisionSummary, error) {
	rows, err := s.db.QueryContext(ctx, `
		SELECT r.id, r.project_id, r.version, r.source, COALESCE(r.preview_key,''),
		       r.compliance, r.created_by, r.created_at,
		       (p.current_revision_id = r.id) AS is_current,
		       COALESCE(jsonb_array_length(r.plan_document->'rooms'), 0) AS room_count
		FROM plan_revisions r
		JOIN projects p ON p.id = r.project_id
		WHERE r.project_id=$1
		ORDER BY r.version DESC
	`, projectID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []RevisionSummary{}
	for rows.Next() {
		var it RevisionSummary
		var previewKey string
		var comp []byte
		var isCurrent sql.NullBool
		if err := rows.Scan(
			&it.ID, &it.ProjectID, &it.Version, &it.Source, &previewKey,
			&comp, &it.CreatedBy, &it.CreatedAt, &isCurrent, &it.RoomCount,
		); err != nil {
			return nil, err
		}
		it.HasPreview = previewKey != ""
		it.IsCurrent = isCurrent.Valid && isCurrent.Bool
		if len(comp) > 0 && string(comp) != "null" {
			var report plancalc.Report
			if json.Unmarshal(comp, &report) == nil && report.Total > 0 {
				score := report.Score
				it.ComplianceScore = &score
				it.ComplianceGrade = report.Grade
			}
		}
		out = append(out, it)
	}
	return out, rows.Err()
}

// SetCurrentRevision makes an existing revision the project's current one, so
// a user can go back to a plan generated earlier. Both ids are checked
// together against the org in a single statement: the UPDATE only matches when
// the project belongs to orgID *and* the revision belongs to that project, so
// a revision id from another org (or another project) can never be attached.
func (s *Service) SetCurrentRevision(ctx context.Context, orgID, projectID, revisionID uuid.UUID) error {
	res, err := s.db.ExecContext(ctx, `
		UPDATE projects p
		SET current_revision_id=$1, status='ready', updated_at=now()
		WHERE p.id=$2 AND p.org_id=$3
		  AND EXISTS (SELECT 1 FROM plan_revisions r WHERE r.id=$1 AND r.project_id=$2)
	`, revisionID, projectID, orgID)
	if err != nil {
		return err
	}
	n, err := res.RowsAffected()
	if err != nil {
		return err
	}
	if n == 0 {
		return ErrNotFound
	}
	return nil
}

func (s *Service) ListRevisions(ctx context.Context, projectID uuid.UUID) ([]domain.PlanRevision, error) {
	rows, err := s.db.QueryContext(ctx, `
		SELECT `+revisionColumns+`
		FROM plan_revisions r WHERE r.project_id=$1 ORDER BY r.version DESC
	`, projectID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []domain.PlanRevision
	for rows.Next() {
		r, err := scanRevision(rows.Scan)
		if err != nil {
			return nil, err
		}
		out = append(out, *r)
	}
	return out, rows.Err()
}

func (s *Service) SaveRevision(ctx context.Context, projectID, userID uuid.UUID, source string, plan json.RawMessage, spec json.RawMessage, previewKey string, baseRevisionID *uuid.UUID) (*domain.PlanRevision, error) {
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return nil, err
	}
	defer func() { _ = tx.Rollback() }()

	var current *uuid.UUID
	var version int
	err = tx.QueryRowContext(ctx, `SELECT current_revision_id FROM projects WHERE id=$1 FOR UPDATE`, projectID).Scan(&current)
	if err != nil {
		return nil, err
	}
	if baseRevisionID != nil {
		if current == nil || *current != *baseRevisionID {
			return nil, ErrConflict
		}
	}
	_ = tx.QueryRowContext(ctx, `SELECT COALESCE(MAX(version),0) FROM plan_revisions WHERE project_id=$1`, projectID).Scan(&version)
	version++

	compliance := plancalc.EvaluateRaw(plan)
	r, err := scanRevision(tx.QueryRowContext(ctx, `
		INSERT INTO plan_revisions (project_id, version, source, plan_document, building_spec, compliance, preview_key, created_by)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
		RETURNING id, project_id, version, source, plan_document, building_spec, COALESCE(preview_key,''), compliance, created_by, created_at
	`, projectID, version, source, plan, nullableJSON(spec), compliance, previewKey, userID).Scan)
	if err != nil {
		return nil, err
	}
	_, err = tx.ExecContext(ctx, `
		UPDATE projects SET current_revision_id=$1, status='ready', updated_at=$2 WHERE id=$3
	`, r.ID, time.Now().UTC(), projectID)
	if err != nil {
		return nil, err
	}
	if err = tx.Commit(); err != nil {
		return nil, err
	}
	return r, nil
}

const revisionColumns = `r.id, r.project_id, r.version, r.source, r.plan_document, r.building_spec, COALESCE(r.preview_key,''), r.compliance, r.created_by, r.created_at`

func scanRevision(scan func(dest ...any) error) (*domain.PlanRevision, error) {
	var r domain.PlanRevision
	var spec, comp []byte
	if err := scan(&r.ID, &r.ProjectID, &r.Version, &r.Source, &r.PlanDocument, &spec, &r.PreviewKey, &comp, &r.CreatedBy, &r.CreatedAt); err != nil {
		return nil, err
	}
	r.BuildingSpec = spec
	if len(comp) > 0 && string(comp) != "null" {
		r.Compliance = comp
	} else {
		r.Compliance = plancalc.EvaluateRaw(r.PlanDocument)
	}
	return &r, nil
}

func attachProjectScore(p *domain.Project, planDoc, stored []byte) {
	if len(planDoc) == 0 {
		return
	}
	var report plancalc.Report
	if len(stored) > 0 && string(stored) != "null" {
		if err := json.Unmarshal(stored, &report); err != nil || report.Total == 0 {
			report = plancalc.Evaluate(planDoc)
		}
	} else {
		report = plancalc.Evaluate(planDoc)
	}
	score := report.Score
	p.ComplianceScore = &score
	p.ComplianceGrade = report.Grade
}

func nullableJSON(b json.RawMessage) any {
	if len(b) == 0 {
		return nil
	}
	return b
}

func (s *Service) Role(ctx context.Context, orgID, userID uuid.UUID) (domain.Role, error) {
	var role domain.Role
	err := s.db.QueryRowContext(ctx, `SELECT role FROM memberships WHERE org_id=$1 AND user_id=$2`, orgID, userID).Scan(&role)
	if errors.Is(err, sql.ErrNoRows) {
		return "", ErrForbidden
	}
	return role, err
}

func EmptyPlanDocument(width, depth float64) json.RawMessage {
	doc := fmt.Sprintf(`{
	  "version":"1.0",
	  "units":"m",
	  "floor":{"level":0,"height_m":2.7,"bounds":{"width":%g,"depth":%g}},
	  "walls":[],
	  "rooms":[],
	  "openings":[]
	}`, width, depth)
	return json.RawMessage(doc)
}
