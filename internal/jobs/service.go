package jobs

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"time"

	"github.com/a-ai/a-ai/internal/domain"
	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
)

const (
	QueueGenerate2D  = "queue:generate_2d"
	QueueGenerate3D  = "queue:generate_3d"
	QueueExport      = "queue:export"
	ChannelEvents    = "events:project:"
	ChannelOrgEvents = "events:org:"
)

var ErrNotFound = errors.New("job not found")

type Service struct {
	db            *sql.DB
	rdb           *redis.Client
	hub           *Hub
	aiURL         string
	internalToken string
	logger        *slog.Logger
	http          *http.Client
}

func NewService(db *sql.DB, rdb *redis.Client, aiURL, internalToken string, logger *slog.Logger) *Service {
	return &Service{
		db:            db,
		rdb:           rdb,
		hub:           NewHub(),
		aiURL:         aiURL,
		internalToken: internalToken,
		logger:        logger,
		http:          &http.Client{Timeout: 420 * time.Second}, // 2× FLUX + vérif VLM peuvent dépasser 5 min
	}
}

// postAI sends a JSON POST to the AI/worker service, authenticated the same
// way the AI service authenticates callbacks into the Go API: a shared
// X-Internal-Token header. The AI service's /v1/* endpoints have no auth of
// their own, and (in the docker-compose deployment) its port is reachable
// directly from the host — without this header anyone who can reach that
// port could drive the pipeline directly, bypassing the Go API's
// authentication, per-org quotas and rate limiting (and running up the
// Together API / GPU bill on the account's dime).
func (s *Service) postAI(ctx context.Context, path string, body []byte) (*http.Response, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, s.aiURL+path, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	if s.internalToken != "" {
		req.Header.Set("X-Internal-Token", s.internalToken)
	}
	return s.http.Do(req)
}

type EnqueueInput struct {
	OrgID     uuid.UUID
	ProjectID uuid.UUID
	Type      string
	Input     map[string]any
	SkipQueue bool // process elsewhere (e.g. inline HTTP); still creates DB job + SSE
}

func (s *Service) Enqueue(ctx context.Context, in EnqueueInput) (*domain.Job, error) {
	raw, _ := json.Marshal(in.Input)
	var j domain.Job
	err := s.db.QueryRowContext(ctx, `
		INSERT INTO jobs (org_id, project_id, type, status, input)
		VALUES ($1,$2,$3,'queued',$4)
		RETURNING id, org_id, project_id, type, status, input, output, COALESCE(error,''), created_at, started_at, finished_at
	`, in.OrgID, in.ProjectID, in.Type, raw).Scan(
		&j.ID, &j.OrgID, &j.ProjectID, &j.Type, &j.Status, &j.Input, &j.Output, &j.Error, &j.CreatedAt, &j.StartedAt, &j.FinishedAt,
	)
	if err != nil {
		return nil, err
	}

	if !in.SkipQueue {
		payload := map[string]any{
			"job_id":     j.ID.String(),
			"type":       j.Type,
			"project_id": j.ProjectID.String(),
			"org_id":     j.OrgID.String(),
			"input":      in.Input,
		}
		b, _ := json.Marshal(payload)
		queue := queueFor(j.Type)
		if err := s.rdb.LPush(ctx, queue, b).Err(); err != nil {
			s.logger.Warn("enqueue redis failed", "err", err, "job_id", j.ID)
		}
	}
	_ = s.Publish(ctx, j.ProjectID, map[string]any{
		"event":      "job.updated",
		"job_id":     j.ID.String(),
		"type":       j.Type,
		"status":     "queued",
		"project_id": j.ProjectID.String(),
		"org_id":     j.OrgID.String(),
	})
	return &j, nil
}

func queueFor(t string) string {
	switch t {
	case "generate_3d":
		return QueueGenerate3D
	case "export":
		return QueueExport
	default:
		return QueueGenerate2D
	}
}

// Get loads a job by id with no ownership check. Only call this from trusted,
// non-end-user-facing code paths (internal worker callbacks authenticated by
// the internal token). Handlers that accept a bare job id from an end user
// MUST use GetForOrg instead, or any authenticated user could read another
// org's job status/output by guessing/enumerating UUIDs (IDOR).
func (s *Service) Get(ctx context.Context, id uuid.UUID) (*domain.Job, error) {
	var j domain.Job
	err := s.db.QueryRowContext(ctx, `
		SELECT id, org_id, project_id, type, status, input, output, COALESCE(error,''), created_at, started_at, finished_at
		FROM jobs WHERE id=$1
	`, id).Scan(
		&j.ID, &j.OrgID, &j.ProjectID, &j.Type, &j.Status, &j.Input, &j.Output, &j.Error, &j.CreatedAt, &j.StartedAt, &j.FinishedAt,
	)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	return &j, err
}

// GetForOrg loads a job only when it belongs to orgID. Use this from
// end-user-facing handlers instead of Get.
func (s *Service) GetForOrg(ctx context.Context, orgID, id uuid.UUID) (*domain.Job, error) {
	var j domain.Job
	err := s.db.QueryRowContext(ctx, `
		SELECT id, org_id, project_id, type, status, input, output, COALESCE(error,''), created_at, started_at, finished_at
		FROM jobs WHERE id=$1 AND org_id=$2
	`, id, orgID).Scan(
		&j.ID, &j.OrgID, &j.ProjectID, &j.Type, &j.Status, &j.Input, &j.Output, &j.Error, &j.CreatedAt, &j.StartedAt, &j.FinishedAt,
	)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	return &j, err
}

type CompleteRequest struct {
	Status string         `json:"status"`
	Output map[string]any `json:"output"`
	Error  string         `json:"error"`
	Step   string         `json:"step"`
}

func (s *Service) Complete(ctx context.Context, id uuid.UUID, req CompleteRequest) error {
	out, _ := json.Marshal(req.Output)
	now := time.Now().UTC()
	_, err := s.db.ExecContext(ctx, `
		UPDATE jobs SET status=$1, output=$2, error=$3, finished_at=$4,
		  started_at = COALESCE(started_at, $4)
		WHERE id=$5
	`, req.Status, out, req.Error, now, id)
	if err != nil {
		return err
	}
	j, err := s.Get(ctx, id)
	if err != nil {
		return err
	}
	_ = s.Publish(ctx, j.ProjectID, map[string]any{
		"event":      "job.updated",
		"job_id":     j.ID.String(),
		"type":       j.Type,
		"status":     req.Status,
		"step":       req.Step,
		"output":     req.Output,
		"error":      req.Error,
		"project_id": j.ProjectID.String(),
		"org_id":     j.OrgID.String(),
	})
	clarify := false
	if req.Output != nil {
		clarify, _ = req.Output["clarify"].(bool)
	}
	if req.Status == "succeeded" && !clarify && (j.Type == "generate_2d" || j.Type == "adapt_plan" || j.Type == "edit_plan") {
		_ = s.Publish(ctx, j.ProjectID, map[string]any{
			"event":       "plan.ready",
			"revision_id": req.Output["revision_id"],
			"preview_url": req.Output["preview_url"],
			"project_id":  j.ProjectID.String(),
			"org_id":      j.OrgID.String(),
		})
	}
	if req.Status == "succeeded" && j.Type == "generate_3d" {
		_ = s.Publish(ctx, j.ProjectID, map[string]any{
			"event":           "model.ready",
			"job_id":          j.ID.String(),
			"glb_artifact_id": req.Output["glb_artifact_id"],
			"obj_artifact_id": req.Output["obj_artifact_id"],
			"artifacts":       req.Output["artifacts"],
			"project_id":      j.ProjectID.String(),
			"org_id":          j.OrgID.String(),
		})
	}
	return nil
}

func (s *Service) MarkRunning(ctx context.Context, id uuid.UUID, step string) error {
	now := time.Now().UTC()
	_, err := s.db.ExecContext(ctx, `
		UPDATE jobs SET status='running', started_at=COALESCE(started_at,$1) WHERE id=$2
	`, now, id)
	if err != nil {
		return err
	}
	j, err := s.Get(ctx, id)
	if err != nil {
		return err
	}
	return s.Publish(ctx, j.ProjectID, map[string]any{
		"event":      "job.updated",
		"job_id":     id.String(),
		"type":       j.Type,
		"status":     "running",
		"step":       step,
		"project_id": j.ProjectID.String(),
		"org_id":     j.OrgID.String(),
	})
}

func (s *Service) Publish(ctx context.Context, projectID uuid.UUID, payload map[string]any) error {
	if payload == nil {
		payload = map[string]any{}
	}
	if _, ok := payload["project_id"]; !ok && projectID != uuid.Nil {
		payload["project_id"] = projectID.String()
	}
	b, _ := json.Marshal(payload)
	orgID, _ := payload["org_id"].(string)

	if s.hub != nil {
		s.hub.Publish("project:"+projectID.String(), b)
		if orgID != "" {
			s.hub.Publish("org:"+orgID, b)
		}
	}
	if s.rdb == nil {
		return nil
	}
	if err := s.rdb.Publish(ctx, ChannelEvents+projectID.String(), b).Err(); err != nil && s.logger != nil {
		s.logger.Warn("redis publish failed", "err", err, "project_id", projectID)
	}
	if orgID != "" {
		_ = s.rdb.Publish(ctx, ChannelOrgEvents+orgID, b).Err()
	}
	return nil
}

// ListenHub subscribes to the in-process hub (topic "project:{id}" or "org:{id}").
func (s *Service) ListenHub(topic string) (<-chan []byte, func()) {
	if s.hub == nil {
		ch := make(chan []byte)
		close(ch)
		return ch, func() {}
	}
	return s.hub.Subscribe(topic)
}

// RunInlineGenerate2D is used when Redis workers are unavailable: call AI HTTP sync.
func (s *Service) RunInlineGenerate2D(ctx context.Context, jobID uuid.UUID, brief string, constraints map[string]any) (map[string]any, error) {
	_ = s.MarkRunning(ctx, jobID, "nlu")
	if constraints == nil {
		constraints = map[string]any{}
	}
	body, _ := json.Marshal(map[string]any{
		"brief":       brief,
		"constraints": constraints,
		"job_id":      jobID.String(),
	})
	resp, err := s.postAI(ctx, "/v1/pipeline", body)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 300 {
		return nil, fmt.Errorf("ai pipeline: %s", string(data))
	}
	var out map[string]any
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// RunInlineEdit retouche le plan courant via /v1/edit (consigne chat).
func (s *Service) RunInlineEdit(ctx context.Context, jobID uuid.UUID, instruction, brief string, spec, plan json.RawMessage, imageB64 string, constraints map[string]any) (map[string]any, error) {
	_ = s.MarkRunning(ctx, jobID, "edit")
	if constraints == nil {
		constraints = map[string]any{}
	}
	if len(spec) == 0 {
		spec = json.RawMessage("{}")
	}
	if len(plan) == 0 {
		plan = json.RawMessage("{}")
	}
	body, _ := json.Marshal(map[string]any{
		"instruction":   instruction,
		"brief":         brief,
		"building_spec": spec,
		"plan_document": plan,
		"image_png_b64": imageB64,
		"constraints":   constraints,
		"job_id":        jobID.String(),
	})
	resp, err := s.postAI(ctx, "/v1/edit", body)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 300 {
		return nil, fmt.Errorf("ai edit: %s", string(data))
	}
	var out map[string]any
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// RunInlineDevis appelle /v1/devis du service IA (cahier des charges + budget + PDF).
func (s *Service) RunInlineDevis(ctx context.Context, jobID uuid.UUID, brief string, spec, plan json.RawMessage, constraints map[string]any) (map[string]any, error) {
	_ = s.MarkRunning(ctx, jobID, "devis")
	if constraints == nil {
		constraints = map[string]any{}
	}
	if len(spec) == 0 {
		spec = json.RawMessage("{}")
	}
	if len(plan) == 0 {
		plan = json.RawMessage("{}")
	}
	body, _ := json.Marshal(map[string]any{
		"brief":         brief,
		"building_spec": spec,
		"plan_document": plan,
		"constraints":   constraints,
	})
	resp, err := s.postAI(ctx, "/v1/devis", body)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 300 {
		return nil, fmt.Errorf("ai devis: %s", string(data))
	}
	var out map[string]any
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func (s *Service) RunInlineAdapt(ctx context.Context, jobID uuid.UUID, plan json.RawMessage, parcel, rules map[string]any) (map[string]any, error) {
	_ = s.MarkRunning(ctx, jobID, "adapt")
	if parcel == nil {
		parcel = map[string]any{}
	}
	if rules == nil {
		rules = map[string]any{}
	}
	var doc any
	if err := json.Unmarshal(plan, &doc); err != nil {
		return nil, err
	}
	body, _ := json.Marshal(map[string]any{"plan_document": doc, "parcel": parcel, "rules": rules})
	resp, err := s.postAI(ctx, "/v1/adapt", body)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 300 {
		return nil, fmt.Errorf("ai adapt: %s", string(data))
	}
	var out map[string]any
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, err
	}
	return out, nil
}
