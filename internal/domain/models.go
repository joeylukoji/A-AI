package domain

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

type Role string

const (
	RoleOwner     Role = "owner"
	RoleArchitect Role = "architect"
	RoleViewer    Role = "viewer"
)

func (r Role) CanEdit() bool {
	return r == RoleOwner || r == RoleArchitect
}

func (r Role) CanBilling() bool {
	return r == RoleOwner
}

type User struct {
	ID           uuid.UUID `json:"id"`
	Email        string    `json:"email"`
	PasswordHash string    `json:"-"`
	Name         string    `json:"name"`
	CreatedAt    time.Time `json:"created_at"`
}

type Org struct {
	ID        uuid.UUID `json:"id"`
	Name      string    `json:"name"`
	Slug      string    `json:"slug"`
	CreatedAt time.Time `json:"created_at"`
}

type Membership struct {
	OrgID  uuid.UUID `json:"org_id"`
	UserID uuid.UUID `json:"user_id"`
	Role   Role      `json:"role"`
}

type Project struct {
	ID                uuid.UUID  `json:"id"`
	OrgID             uuid.UUID  `json:"org_id"`
	Name              string     `json:"name"`
	Brief             string     `json:"brief"`
	Status            string     `json:"status"`
	CurrentRevisionID *uuid.UUID `json:"current_revision_id,omitempty"`
	CreatedBy         uuid.UUID  `json:"created_by"`
	CreatedAt         time.Time  `json:"created_at"`
	UpdatedAt         time.Time  `json:"updated_at"`
	ComplianceScore   *int       `json:"compliance_score,omitempty"`
	ComplianceGrade   string     `json:"compliance_grade,omitempty"`
}

// Score returns the compliance score as a plain int, 0 when the project has no
// scored revision. Templates need this: html/template's ge/lt refuse a *int
// ("invalid type for comparison") and the resulting execution error truncates
// the page mid-tag, so projects.html must compare Score, never
// ComplianceScore. The pointer field stays for the JSON API, where the
// distinction between "no report" and "scored 0" is meaningful.
func (p Project) Score() int {
	if p.ComplianceScore == nil {
		return 0
	}
	return *p.ComplianceScore
}

type PlanRevision struct {
	ID           uuid.UUID       `json:"id"`
	ProjectID    uuid.UUID       `json:"project_id"`
	Version      int             `json:"version"`
	Source       string          `json:"source"`
	PlanDocument json.RawMessage `json:"plan_document"`
	BuildingSpec json.RawMessage `json:"building_spec,omitempty"`
	Compliance   json.RawMessage `json:"compliance,omitempty"`
	PreviewKey   string          `json:"preview_key,omitempty"`
	CreatedBy    uuid.UUID       `json:"created_by"`
	CreatedAt    time.Time       `json:"created_at"`
}

type Job struct {
	ID         uuid.UUID       `json:"id"`
	OrgID      uuid.UUID       `json:"org_id"`
	ProjectID  uuid.UUID       `json:"project_id"`
	Type       string          `json:"type"`
	Status     string          `json:"status"`
	Input      json.RawMessage `json:"input"`
	Output     json.RawMessage `json:"output"`
	Error      string          `json:"error,omitempty"`
	CreatedAt  time.Time       `json:"created_at"`
	StartedAt  *time.Time      `json:"started_at,omitempty"`
	FinishedAt *time.Time      `json:"finished_at,omitempty"`
}

type Artifact struct {
	ID             uuid.UUID  `json:"id"`
	ProjectID      uuid.UUID  `json:"project_id"`
	RevisionID     *uuid.UUID `json:"revision_id,omitempty"`
	JobID          *uuid.UUID `json:"job_id,omitempty"`
	Kind           string     `json:"kind"`
	StorageKey     string     `json:"storage_key"`
	ContentType    string     `json:"content_type"`
	ChecksumSHA256 string     `json:"checksum_sha256,omitempty"`
	Bytes          int64      `json:"bytes"`
	CreatedAt      time.Time  `json:"created_at"`
}

type Subscription struct {
	ID                   uuid.UUID
	OrgID                uuid.UUID
	Plan                 string
	StripeCustomerID     string
	StripeSubscriptionID string
	Status               string
	CurrentPeriodEnd     *time.Time
}

type UsageQuota struct {
	OrgID           uuid.UUID
	PeriodStart     time.Time
	GenerationsUsed int
	ExportsUsed     int
	GPUMinutesUsed  float64
}

type PlanLimits struct {
	Generations int
	Exports     int
	Generate3D  int
}

func LimitsForPlan(plan string) PlanLimits {
	switch plan {
	case "pro":
		return PlanLimits{Generations: 50, Exports: 500, Generate3D: 30}
	case "bureau":
		return PlanLimits{Generations: 300, Exports: 5000, Generate3D: 200}
	default:
		return PlanLimits{Generations: 5, Exports: 5, Generate3D: 2}
	}
}
