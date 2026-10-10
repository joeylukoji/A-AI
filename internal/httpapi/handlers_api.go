package httpapi

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/a-ai/a-ai/internal/artifact"
	"github.com/a-ai/a-ai/internal/billing"
	"github.com/a-ai/a-ai/internal/domain"
	"github.com/a-ai/a-ai/internal/export"
	"github.com/a-ai/a-ai/internal/jobs"
	"github.com/a-ai/a-ai/internal/plan"
	"github.com/a-ai/a-ai/internal/project"
	"github.com/google/uuid"
)

// maxJSONBodyBytes caps request bodies decoded as JSON. It guards against a
// client (malicious or buggy) streaming an unbounded body to exhaust server
// memory; every legitimate payload on this API (plan documents included) is
// well under this size.
const maxJSONBodyBytes = 4 << 20 // 4 MiB

// decodeJSONBody decodes a JSON body into v, rejecting bodies larger than
// maxJSONBodyBytes before they are fully buffered in memory.
func decodeJSONBody(w http.ResponseWriter, r *http.Request, v any) error {
	r.Body = http.MaxBytesReader(w, r.Body, maxJSONBodyBytes)
	return json.NewDecoder(r.Body).Decode(v)
}

// internalError logs the full error server-side (with request context) and
// returns a generic message to the client — SQL errors, file paths and other
// internal details must never leak through the public API.
func (s *Server) internalError(w http.ResponseWriter, r *http.Request, err error) {
	s.log.Error("internal error", "method", r.Method, "path", r.URL.Path, "err", err)
	writeErr(w, http.StatusInternalServerError, "internal", "une erreur interne est survenue")
}

// upstreamError is internalError's counterpart for failures talking to a
// downstream dependency (object storage, AI/worker services): still logged in
// full server-side, still generic to the client.
func (s *Server) upstreamError(w http.ResponseWriter, r *http.Request, err error) {
	s.log.Error("upstream error", "method", r.Method, "path", r.URL.Path, "err", err)
	writeErr(w, http.StatusBadGateway, "upstream", "service temporairement indisponible")
}

func (s *Server) handleMe(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	writeJSON(w, http.StatusOK, map[string]any{
		"user": map[string]any{"id": p.User.ID, "email": p.User.Email, "name": p.User.Name},
		"org":  map[string]any{"id": p.Org.ID, "name": p.Org.Name, "slug": p.Org.Slug},
		"role": p.Role,
	})
}

func (s *Server) handleListProjects(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	list, err := s.projects.List(r.Context(), p.Org.ID)
	if err != nil {
		s.internalError(w, r, err)
		return
	}
	writeJSON(w, 200, map[string]any{"projects": list})
}

func (s *Server) handleCreateProjectAPI(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	if !p.Role.CanEdit() {
		writeErr(w, 403, "forbidden", "insufficient role")
		return
	}
	var body struct {
		Name  string `json:"name"`
		Brief string `json:"brief"`
	}
	if err := decodeJSONBody(w, r, &body); err != nil {
		writeErr(w, 400, "invalid_json", "invalid body")
		return
	}
	proj, err := s.projects.Create(r.Context(), p.Org.ID, p.User.ID, body.Name, body.Brief)
	if err != nil {
		s.internalError(w, r, err)
		return
	}
	writeJSON(w, 201, proj)
}

func (s *Server) handleGetProject(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	id, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		writeErr(w, 404, "not_found", "project not found")
		return
	}
	proj, err := s.projects.Get(r.Context(), p.Org.ID, id)
	if err != nil {
		writeErr(w, 404, "not_found", "project not found")
		return
	}
	var rev *domain.PlanRevision
	if proj.CurrentRevisionID != nil {
		rev, _ = s.projects.GetRevision(r.Context(), *proj.CurrentRevisionID)
	}
	writeJSON(w, 200, map[string]any{"project": proj, "revision": rev})
}

func (s *Server) handleGenerate2D(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	if !p.Role.CanEdit() {
		writeErr(w, 403, "forbidden", "insufficient role")
		return
	}
	id, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		writeErr(w, 404, "not_found", "project not found")
		return
	}
	proj, err := s.projects.Get(r.Context(), p.Org.ID, id)
	if err != nil {
		writeErr(w, 404, "not_found", "project not found")
		return
	}
	if err := s.billing.EnsureQuota(r.Context(), p.Org.ID, "generate_2d"); err != nil {
		if errors.Is(err, billing.ErrQuotaExceeded) {
			writeErr(w, 402, "quota_exceeded", err.Error())
			return
		}
		s.internalError(w, r, err)
		return
	}
	var body struct {
		Brief        string         `json:"brief"`
		Constraints  map[string]any `json:"constraints"`
		ParcelWidthM *float64       `json:"parcel_width_m"`
		ParcelDepthM *float64       `json:"parcel_depth_m"`
		SetbackM     *float64       `json:"setback_m"`
		Careful      bool           `json:"careful"`
	}
	_ = decodeJSONBody(w, r, &body)
	if body.Brief == "" {
		body.Brief = proj.Brief
	}
	if body.Constraints == nil {
		body.Constraints = map[string]any{}
	}
	if body.ParcelWidthM != nil {
		body.Constraints["parcel_width_m"] = *body.ParcelWidthM
	}
	if body.ParcelDepthM != nil {
		body.Constraints["parcel_depth_m"] = *body.ParcelDepthM
	}
	if body.SetbackM != nil {
		body.Constraints["setback_m"] = *body.SetbackM
	}
	if body.Careful {
		body.Constraints["careful"] = true
	}
	_ = s.projects.UpdateBrief(r.Context(), p.Org.ID, id, body.Brief)
	_ = s.projects.SetStatus(r.Context(), id, "generating")

	job, err := s.jobs.Enqueue(r.Context(), jobs.EnqueueInput{
		OrgID: p.Org.ID, ProjectID: id, Type: "generate_2d",
		Input:     map[string]any{"brief": body.Brief, "constraints": body.Constraints, "user_id": p.User.ID.String()},
		SkipQueue: true, // processed inline via FastAPI to avoid double-consume with Redis worker
	})
	if err != nil {
		s.internalError(w, r, err)
		return
	}
	_ = s.billing.Increment(r.Context(), p.Org.ID, "generate_2d")

	go s.processGenerate2D(job.ID, id, p.User.ID, body.Brief, body.Constraints)

	writeJSON(w, 202, map[string]any{"job_id": job.ID, "status": "queued"})
}

func (s *Server) handleEditPlan(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	if !p.Role.CanEdit() {
		writeErr(w, 403, "forbidden", "insufficient role")
		return
	}
	id, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		writeErr(w, 404, "not_found", "project not found")
		return
	}
	proj, err := s.projects.Get(r.Context(), p.Org.ID, id)
	if err != nil {
		writeErr(w, 404, "not_found", "project not found")
		return
	}
	if proj.CurrentRevisionID == nil {
		writeErr(w, 400, "no_plan", "générez un plan avant de le modifier")
		return
	}
	rev, err := s.projects.GetRevision(r.Context(), *proj.CurrentRevisionID)
	if err != nil {
		writeErr(w, 404, "not_found", "revision not found")
		return
	}
	if err := s.billing.EnsureQuota(r.Context(), p.Org.ID, "generate_2d"); err != nil {
		if errors.Is(err, billing.ErrQuotaExceeded) {
			writeErr(w, 402, "quota_exceeded", err.Error())
			return
		}
		s.internalError(w, r, err)
		return
	}
	var body struct {
		Instruction string `json:"instruction"`
		Message     string `json:"message"`
	}
	_ = decodeJSONBody(w, r, &body)
	instruction := strings.TrimSpace(body.Instruction)
	if instruction == "" {
		instruction = strings.TrimSpace(body.Message)
	}
	if instruction == "" {
		writeErr(w, 400, "invalid", "indiquez la modification souhaitée")
		return
	}
	if len(instruction) > 800 {
		instruction = instruction[:800]
	}
	job, err := s.jobs.Enqueue(r.Context(), jobs.EnqueueInput{
		OrgID: p.Org.ID, ProjectID: id, Type: "edit_plan",
		Input:     map[string]any{"instruction": instruction, "user_id": p.User.ID.String()},
		SkipQueue: true,
	})
	if err != nil {
		s.internalError(w, r, err)
		return
	}
	_ = s.billing.Increment(r.Context(), p.Org.ID, "generate_2d")
	_ = s.projects.SetStatus(r.Context(), id, "generating")
	go s.processEditPlan(job.ID, id, p.User.ID, proj.Brief, instruction, rev)
	writeJSON(w, 202, map[string]any{"job_id": job.ID, "status": "queued"})
}

func (s *Server) processEditPlan(jobID, projectID, userID uuid.UUID, brief, instruction string, rev *domain.PlanRevision) {
	ctx := context.Background()
	projectStatusOnFailure := "draft"
	if rev != nil {
		projectStatusOnFailure = "ready"
	}
	imageB64 := ""
	if rev != nil && rev.PreviewKey != "" && s.storage != nil {
		if data, _, err := s.storage.Get(ctx, rev.PreviewKey); err == nil && len(data) > 0 {
			imageB64 = base64.StdEncoding.EncodeToString(data)
		}
	}
	specRaw, planRaw := json.RawMessage("{}"), json.RawMessage("{}")
	if rev != nil {
		if len(rev.BuildingSpec) > 0 {
			specRaw = rev.BuildingSpec
		}
		if len(rev.PlanDocument) > 0 {
			planRaw = rev.PlanDocument
		}
	}
	out, err := s.jobs.RunInlineEdit(ctx, jobID, instruction, brief, specRaw, planRaw, imageB64, map[string]any{})
	if err != nil {
		_ = s.jobs.Complete(ctx, jobID, jobs.CompleteRequest{Status: "failed", Error: err.Error(), Step: "edit"})
		_ = s.projects.SetStatus(ctx, projectID, projectStatusOnFailure)
		return
	}
	reply, _ := out["reply_fr"].(string)
	if clarify, _ := out["clarify"].(bool); clarify {
		_ = s.projects.SetStatus(ctx, projectID, "ready")
		_ = s.jobs.Complete(ctx, jobID, jobs.CompleteRequest{
			Status: "succeeded",
			Step:   "edit",
			Output: map[string]any{"clarify": true, "reply_fr": reply},
		})
		return
	}
	planOut, _ := json.Marshal(out["plan_document"])
	specOut, _ := json.Marshal(out["building_spec"])
	previewKey := ""
	if rev != nil {
		previewKey = rev.PreviewKey
	}
	if b64, ok := out["image_png_b64"].(string); ok && b64 != "" {
		if key := s.persistPreviewPNG(ctx, projectID, b64, ""); key != "" {
			previewKey = key
		}
	}
	var baseRevisionID *uuid.UUID
	if rev != nil {
		baseRevisionID = &rev.ID
	}
	saved, err := s.projects.SaveRevision(ctx, projectID, userID, "ai", planOut, specOut, previewKey, baseRevisionID)
	if err != nil {
		if errors.Is(err, project.ErrConflict) {
			_ = s.projects.SetStatus(ctx, projectID, "ready")
			_ = s.jobs.Complete(ctx, jobID, jobs.CompleteRequest{
				Status: "failed",
				Error:  "revision_conflict",
				Step:   "edit",
			})
			return
		}
		_ = s.jobs.Complete(ctx, jobID, jobs.CompleteRequest{Status: "failed", Error: err.Error()})
		_ = s.projects.SetStatus(ctx, projectID, projectStatusOnFailure)
		return
	}
	_ = s.jobs.Complete(ctx, jobID, jobs.CompleteRequest{
		Status: "succeeded",
		Step:   "edit",
		Output: map[string]any{
			"revision_id": saved.ID.String(),
			"version":     saved.Version,
			"preview_url": "/api/v1/projects/" + projectID.String() + "/preview",
			"reply_fr":    reply,
		},
	})
}

func (s *Server) handleAdaptPlan(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	if !p.Role.CanEdit() {
		writeErr(w, 403, "forbidden", "insufficient role")
		return
	}
	id, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		writeErr(w, 404, "not_found", "project not found")
		return
	}
	proj, err := s.projects.Get(r.Context(), p.Org.ID, id)
	if err != nil || proj.CurrentRevisionID == nil {
		writeErr(w, 400, "no_plan", "générez un plan avant d’adapter")
		return
	}
	rev, err := s.projects.GetRevision(r.Context(), *proj.CurrentRevisionID)
	if err != nil {
		writeErr(w, 404, "not_found", "revision not found")
		return
	}
	var body struct {
		ParcelWidthM *float64       `json:"parcel_width_m"`
		ParcelDepthM *float64       `json:"parcel_depth_m"`
		SetbackM     *float64       `json:"setback_m"`
		Rules        map[string]any `json:"rules"`
	}
	_ = decodeJSONBody(w, r, &body)
	parcel := map[string]any{}
	if body.ParcelWidthM != nil {
		parcel["width_m"] = *body.ParcelWidthM
	}
	if body.ParcelDepthM != nil {
		parcel["depth_m"] = *body.ParcelDepthM
	}
	if body.SetbackM != nil {
		parcel["setback_m"] = *body.SetbackM
	}
	job, err := s.jobs.Enqueue(r.Context(), jobs.EnqueueInput{
		OrgID: p.Org.ID, ProjectID: id, Type: "adapt_plan",
		Input:     map[string]any{"parcel": parcel, "user_id": p.User.ID.String()},
		SkipQueue: true,
	})
	if err != nil {
		s.internalError(w, r, err)
		return
	}
	go s.processAdaptPlan(job.ID, id, p.User.ID, rev.PlanDocument, parcel, body.Rules)
	writeJSON(w, 202, map[string]any{"job_id": job.ID, "status": "queued"})
}

func (s *Server) processAdaptPlan(jobID, projectID, userID uuid.UUID, plan json.RawMessage, parcel, rules map[string]any) {
	ctx := context.Background()
	out, err := s.jobs.RunInlineAdapt(ctx, jobID, plan, parcel, rules)
	if err != nil {
		_ = s.jobs.Complete(ctx, jobID, jobs.CompleteRequest{Status: "failed", Error: err.Error(), Step: "adapt"})
		return
	}
	planRaw, _ := json.Marshal(out["plan_document"])
	specRaw, _ := json.Marshal(map[string]any{
		"version":    "1.0",
		"brief":      "adapt",
		"rooms":      []any{},
		"parcel":     out["parcel"],
		"dimensions": out["dimensions"],
		"rules":      out["rules"],
	})
	rev, err := s.projects.SaveRevision(ctx, projectID, userID, "ai", planRaw, specRaw, "", nil)
	if err != nil {
		_ = s.jobs.Complete(ctx, jobID, jobs.CompleteRequest{Status: "failed", Error: err.Error()})
		return
	}
	_ = s.jobs.Complete(ctx, jobID, jobs.CompleteRequest{
		Status: "succeeded",
		Step:   "adapt",
		Output: map[string]any{
			"revision_id": rev.ID.String(),
			"version":     rev.Version,
			"compliance":  out["compliance"],
			"dimensions":  out["dimensions"],
			"parcel":      out["parcel"],
		},
	})
}

func (s *Server) processGenerate2D(jobID, projectID, userID uuid.UUID, brief string, constraints map[string]any) {
	ctx := context.Background()
	out, err := s.jobs.RunInlineGenerate2D(ctx, jobID, brief, constraints)
	if err != nil {
		_ = s.jobs.Complete(ctx, jobID, jobs.CompleteRequest{Status: "failed", Error: err.Error(), Step: "pipeline"})
		_ = s.projects.SetStatus(ctx, projectID, "draft")
		return
	}
	planRaw, _ := json.Marshal(out["plan_document"])
	specRaw, _ := json.Marshal(out["building_spec"])
	previewKey, _ := out["preview_key"].(string)
	if b64, ok := out["image_png_b64"].(string); ok {
		previewKey = s.persistPreviewPNG(ctx, projectID, b64, previewKey)
	}
	rev, err := s.projects.SaveRevision(ctx, projectID, userID, "ai", planRaw, specRaw, previewKey, nil)
	if err != nil {
		_ = s.jobs.Complete(ctx, jobID, jobs.CompleteRequest{Status: "failed", Error: err.Error()})
		return
	}
	_ = s.jobs.Complete(ctx, jobID, jobs.CompleteRequest{
		Status: "succeeded",
		Step:   "vectorize",
		Output: map[string]any{
			"revision_id": rev.ID.String(),
			"version":     rev.Version,
			"preview_url": "/api/v1/revisions/" + rev.ID.String(),
			"preview_key": previewKey,
			"compliance":  json.RawMessage(rev.Compliance),
		},
	})
}

func (s *Server) handleGenerateDevis(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	if !p.Role.CanEdit() {
		writeErr(w, 403, "forbidden", "insufficient role")
		return
	}
	id, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		writeErr(w, 404, "not_found", "project not found")
		return
	}
	proj, err := s.projects.Get(r.Context(), p.Org.ID, id)
	if err != nil {
		writeErr(w, 404, "not_found", "project not found")
		return
	}
	if err := s.billing.EnsureQuota(r.Context(), p.Org.ID, "generate_devis"); err != nil {
		if errors.Is(err, billing.ErrQuotaExceeded) {
			writeErr(w, 402, "quota_exceeded", err.Error())
			return
		}
		s.internalError(w, r, err)
		return
	}
	var specRaw, planRaw json.RawMessage
	var constraints map[string]any
	if proj.CurrentRevisionID != nil {
		if rev, rerr := s.projects.GetRevision(r.Context(), *proj.CurrentRevisionID); rerr == nil {
			specRaw = rev.BuildingSpec
			planRaw = rev.PlanDocument
		}
	}
	job, err := s.jobs.Enqueue(r.Context(), jobs.EnqueueInput{
		OrgID: p.Org.ID, ProjectID: id, Type: "generate_devis",
		Input:     map[string]any{"brief": proj.Brief, "user_id": p.User.ID.String()},
		SkipQueue: true,
	})
	if err != nil {
		s.internalError(w, r, err)
		return
	}
	_ = s.billing.Increment(r.Context(), p.Org.ID, "generate_devis")

	go s.processGenerateDevis(job.ID, id, proj.Brief, specRaw, planRaw, constraints)

	writeJSON(w, 202, map[string]any{"job_id": job.ID, "status": "queued"})
}

func (s *Server) processGenerateDevis(jobID, projectID uuid.UUID, brief string, specRaw, planRaw json.RawMessage, constraints map[string]any) {
	ctx := context.Background()
	out, err := s.jobs.RunInlineDevis(ctx, jobID, brief, specRaw, planRaw, constraints)
	if err != nil {
		_ = s.jobs.Complete(ctx, jobID, jobs.CompleteRequest{Status: "failed", Error: err.Error(), Step: "devis"})
		return
	}
	pdfB64, _ := out["pdf_base64"].(string)
	pdfRaw, derr := base64.StdEncoding.DecodeString(pdfB64)
	if derr != nil || len(pdfRaw) == 0 {
		_ = s.jobs.Complete(ctx, jobID, jobs.CompleteRequest{Status: "failed", Error: "pdf invalide", Step: "devis"})
		return
	}
	key := s.storage.Key(projectID, "devis", "pdf")
	if err := s.storage.Put(ctx, key, "application/pdf", pdfRaw); err != nil {
		_ = s.jobs.Complete(ctx, jobID, jobs.CompleteRequest{Status: "failed", Error: err.Error(), Step: "devis"})
		return
	}
	art, err := s.artifacts.Create(ctx, artifact.CreateInput{
		ProjectID:   projectID,
		JobID:       &jobID,
		Kind:        "devis",
		StorageKey:  key,
		ContentType: "application/pdf",
		Bytes:       int64(len(pdfRaw)),
	})
	if err != nil {
		_ = s.jobs.Complete(ctx, jobID, jobs.CompleteRequest{Status: "failed", Error: err.Error(), Step: "devis"})
		return
	}
	_ = s.jobs.Complete(ctx, jobID, jobs.CompleteRequest{
		Status: "succeeded",
		Step:   "devis",
		Output: map[string]any{
			"artifact_id": art.ID.String(),
			"download":    "/api/v1/artifacts/" + art.ID.String() + "/content",
			"devis":       out["devis"],
		},
	})
}

func (s *Server) handleGenerate3D(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	if !p.Role.CanEdit() {
		writeErr(w, 403, "forbidden", "insufficient role")
		return
	}
	id, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		writeErr(w, 404, "not_found", "project not found")
		return
	}
	proj, err := s.projects.Get(r.Context(), p.Org.ID, id)
	if err != nil || proj.CurrentRevisionID == nil {
		writeErr(w, 400, "no_plan", "generate a plan first")
		return
	}
	if err := s.billing.EnsureQuota(r.Context(), p.Org.ID, "generate_3d"); err != nil {
		if errors.Is(err, billing.ErrQuotaExceeded) {
			writeErr(w, 402, "quota_exceeded", err.Error())
			return
		}
		// Fail closed: a quota-check error (e.g. DB hiccup) must not silently
		// let the job through unmetered.
		s.internalError(w, r, err)
		return
	}
	rev, err := s.projects.GetRevision(r.Context(), *proj.CurrentRevisionID)
	if err != nil {
		writeErr(w, 404, "not_found", "revision not found")
		return
	}
	job, err := s.jobs.Enqueue(r.Context(), jobs.EnqueueInput{
		OrgID: p.Org.ID, ProjectID: id, Type: "generate_3d",
		Input: map[string]any{
			"revision_id":   rev.ID.String(),
			"plan_document": json.RawMessage(rev.PlanDocument),
			"user_id":       p.User.ID.String(),
		},
	})
	if err != nil {
		s.internalError(w, r, err)
		return
	}
	_ = s.billing.Increment(r.Context(), p.Org.ID, "generate_3d")
	writeJSON(w, 202, map[string]any{"job_id": job.ID, "status": "queued"})
}

func (s *Server) handleSavePlan(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	if !p.Role.CanEdit() {
		writeErr(w, 403, "forbidden", "insufficient role")
		return
	}
	id, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		writeErr(w, 404, "not_found", "project not found")
		return
	}
	if _, err := s.projects.Get(r.Context(), p.Org.ID, id); err != nil {
		writeErr(w, 404, "not_found", "project not found")
		return
	}
	var body struct {
		PlanDocument   json.RawMessage `json:"plan_document"`
		BaseRevisionID *uuid.UUID      `json:"base_revision_id"`
	}
	if err := decodeJSONBody(w, r, &body); err != nil || len(body.PlanDocument) == 0 {
		writeErr(w, 400, "invalid_json", "plan_document required")
		return
	}
	if err := plan.Validate(body.PlanDocument); err != nil {
		writeErr(w, 400, "invalid_plan", err.Error())
		return
	}
	rev, err := s.projects.SaveRevision(r.Context(), id, p.User.ID, "editor", body.PlanDocument, nil, "", body.BaseRevisionID)
	if errors.Is(err, project.ErrConflict) {
		writeErr(w, 409, "conflict", "revision conflict")
		return
	}
	if err != nil {
		s.internalError(w, r, err)
		return
	}
	writeJSON(w, 200, rev)
}

// handleRestoreRevision makes a previously generated plan the current one.
// Generating a new plan never deletes the old revisions (they are all in
// plan_revisions); this is what lets a user actually go back to one.
func (s *Server) handleRestoreRevision(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	if !p.Role.CanEdit() {
		writeErr(w, http.StatusForbidden, "forbidden", "insufficient role")
		return
	}
	projectID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		writeErr(w, 404, "not_found", "project not found")
		return
	}
	revisionID, err := uuid.Parse(r.PathValue("revisionID"))
	if err != nil {
		writeErr(w, 404, "not_found", "revision not found")
		return
	}
	// SetCurrentRevision checks org ownership and the project/revision pairing
	// in one statement, so no extra lookup is needed here.
	if err := s.projects.SetCurrentRevision(r.Context(), p.Org.ID, projectID, revisionID); err != nil {
		if errors.Is(err, project.ErrNotFound) {
			writeErr(w, 404, "not_found", "revision not found")
			return
		}
		s.internalError(w, r, err)
		return
	}
	writeJSON(w, 200, map[string]any{"ok": true, "current_revision_id": revisionID})
}

func (s *Server) handleListRevisions(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	id, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		writeErr(w, 404, "not_found", "project not found")
		return
	}
	if _, err := s.projects.Get(r.Context(), p.Org.ID, id); err != nil {
		writeErr(w, 404, "not_found", "project not found")
		return
	}
	list, err := s.projects.ListRevisions(r.Context(), id)
	if err != nil {
		s.internalError(w, r, err)
		return
	}
	writeJSON(w, 200, map[string]any{"revisions": list})
}

func (s *Server) handleProjectPreview(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	id, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		writeErr(w, 404, "not_found", "project not found")
		return
	}
	proj, err := s.projects.Get(r.Context(), p.Org.ID, id)
	if err != nil || proj.CurrentRevisionID == nil {
		writeErr(w, 404, "not_found", "preview not found")
		return
	}
	rev, err := s.projects.GetRevision(r.Context(), *proj.CurrentRevisionID)
	if err != nil || rev.PreviewKey == "" || s.storage == nil {
		writeErr(w, 404, "not_found", "preview not found")
		return
	}
	data, ct, err := s.storage.Get(r.Context(), rev.PreviewKey)
	if err != nil {
		writeErr(w, 404, "not_found", "preview not found")
		return
	}
	if ct == "" {
		ct = "image/png"
	}
	w.Header().Set("Content-Type", ct)
	w.Header().Set("Cache-Control", "private, no-store, must-revalidate")
	w.WriteHeader(200)
	_, _ = w.Write(data)
}

func (s *Server) handleGetRevision(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	id, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		writeErr(w, 404, "not_found", "revision not found")
		return
	}
	// GetRevisionForOrg (not GetRevision): the revision id comes straight from
	// the URL, so without the org filter any authenticated user could read
	// another org's plan by guessing/enumerating a UUID (IDOR).
	rev, err := s.projects.GetRevisionForOrg(r.Context(), p.Org.ID, id)
	if err != nil {
		writeErr(w, 404, "not_found", "revision not found")
		return
	}
	writeJSON(w, 200, rev)
}

func (s *Server) handleListArtifacts(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	id, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		writeErr(w, 404, "not_found", "project not found")
		return
	}
	if _, err := s.projects.Get(r.Context(), p.Org.ID, id); err != nil {
		writeErr(w, 404, "not_found", "project not found")
		return
	}
	kind := r.URL.Query().Get("kind")
	list, err := s.artifacts.ListByProject(r.Context(), id, kind)
	if err != nil {
		s.internalError(w, r, err)
		return
	}
	writeJSON(w, 200, map[string]any{"artifacts": list})
}

func (s *Server) handleArtifactContent(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	id, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		writeErr(w, 404, "not_found", "artifact not found")
		return
	}
	art, err := s.artifacts.Get(r.Context(), id)
	if err != nil {
		if errors.Is(err, artifact.ErrNotFound) {
			writeErr(w, 404, "not_found", "artifact not found")
			return
		}
		s.internalError(w, r, err)
		return
	}
	if _, err := s.projects.Get(r.Context(), p.Org.ID, art.ProjectID); err != nil {
		writeErr(w, 404, "not_found", "artifact not found")
		return
	}
	data, ct, err := s.storage.Get(r.Context(), art.StorageKey)
	if err != nil {
		s.upstreamError(w, r, err)
		return
	}
	if ct == "" {
		ct = art.ContentType
	}
	w.Header().Set("Content-Type", ct)
	w.Header().Set("Cache-Control", "private, max-age=3600")
	w.WriteHeader(200)
	_, _ = w.Write(data)
}

func (s *Server) handleGetJob(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	id, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		writeErr(w, 404, "not_found", "job not found")
		return
	}
	// GetForOrg (not Get): the job id comes straight from the URL, so without
	// the org filter any authenticated user could read another org's job
	// status/output (including instructions, revision ids, etc.) by
	// guessing/enumerating a UUID (IDOR).
	j, err := s.jobs.GetForOrg(r.Context(), p.Org.ID, id)
	if err != nil {
		writeErr(w, 404, "not_found", "job not found")
		return
	}
	view := *j
	view.Error = jobs.PublicError(j.Error) // branded copy; raw string stays in DB
	writeJSON(w, 200, view)
}

func (s *Server) handleExport(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	if !p.Role.CanEdit() {
		writeErr(w, 403, "forbidden", "insufficient role")
		return
	}
	id, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		writeErr(w, 404, "not_found", "revision not found")
		return
	}
	if err := s.billing.EnsureQuota(r.Context(), p.Org.ID, "export"); err != nil {
		if errors.Is(err, billing.ErrQuotaExceeded) {
			writeErr(w, 402, "quota_exceeded", err.Error())
			return
		}
		// Fail closed: a quota-check error (e.g. DB hiccup) must not silently
		// let the export through unmetered.
		s.internalError(w, r, err)
		return
	}
	// GetRevisionForOrg (not GetRevision): the revision id comes straight from
	// the URL, so without the org filter any authenticated user could export
	// another org's plan by guessing/enumerating a UUID (IDOR).
	rev, err := s.projects.GetRevisionForOrg(r.Context(), p.Org.ID, id)
	if err != nil {
		writeErr(w, 404, "not_found", "revision not found")
		return
	}
	var body struct {
		Format string `json:"format"`
	}
	_ = decodeJSONBody(w, r, &body)
	if body.Format == "" {
		body.Format = "svg"
	}
	doc, err := export.Parse(rev.PlanDocument)
	if err != nil {
		writeErr(w, 400, "invalid_plan", err.Error())
		return
	}
	res, err := export.Export(doc, body.Format)
	if err != nil {
		writeErr(w, 400, "unsupported", err.Error())
		return
	}
	_ = s.billing.Increment(r.Context(), p.Org.ID, "export")
	sum := sha256.Sum256(res.Data)
	key := s.storage.Key(rev.ProjectID, "export-"+body.Format, extFor(body.Format))
	if err := s.storage.Put(r.Context(), key, res.ContentType, res.Data); err != nil {
		// Best-effort cache of the export in object storage: the download
		// below still succeeds, so just log and move on.
		s.log.Warn("export storage put failed", "revision_id", rev.ID, "err", err)
	}

	w.Header().Set("Content-Type", res.ContentType)
	w.Header().Set("Content-Length", strconv.Itoa(len(res.Data)))
	w.Header().Set("Content-Disposition", fmt.Sprintf(`attachment; filename="%s"`, res.Filename))
	w.Header().Set("X-Checksum-SHA256", hex.EncodeToString(sum[:]))
	if res.Tool != "" {
		w.Header().Set("X-CAD-Tool", res.Tool)
	}
	w.WriteHeader(200)
	_, _ = w.Write(res.Data)
}

func extFor(format string) string {
	switch strings.ToLower(format) {
	case "gltf", "glb":
		return "gltf"
	default:
		return strings.ToLower(format)
	}
}

func (s *Server) handleUsage(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	sub, _ := s.billing.GetSubscription(r.Context(), p.Org.ID)
	usage, _ := s.billing.Usage(r.Context(), p.Org.ID)
	writeJSON(w, 200, map[string]any{
		"plan":   sub.Plan,
		"usage":  usage,
		"limits": domain.LimitsForPlan(sub.Plan),
	})
}

func (s *Server) handleCheckout(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	if !p.Role.CanBilling() {
		writeErr(w, 403, "forbidden", "owner only")
		return
	}
	var body struct {
		Plan string `json:"plan"`
	}
	_ = decodeJSONBody(w, r, &body)
	if body.Plan == "" {
		body.Plan = "pro"
	}
	url := s.billing.CheckoutURL(p.Org.ID, body.Plan)
	if !s.billing.StripeEnabled() {
		_ = s.billing.SetPlan(r.Context(), p.Org.ID, body.Plan)
	}
	writeJSON(w, 200, map[string]any{"url": url})
}

func (s *Server) handleStripeWebhook(w http.ResponseWriter, r *http.Request) {
	// Unauthenticated endpoint (webhook signature verification isn't wired up
	// yet): bound the read so a caller can't force us to buffer an unbounded
	// body.
	_, _ = io.Copy(io.Discard, io.LimitReader(r.Body, maxJSONBodyBytes))
	// Stub: acknowledge webhooks when Stripe is wired.
	writeJSON(w, 200, map[string]string{"received": "ok"})
}

func (s *Server) handleOrgSSE(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	s.streamSSE(w, r, "org:"+p.Org.ID.String())
}

func (s *Server) handleSSE(w http.ResponseWriter, r *http.Request) {
	p := principal(r)
	id, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		writeErr(w, 404, "not_found", "project not found")
		return
	}
	if _, err := s.projects.Get(r.Context(), p.Org.ID, id); err != nil {
		writeErr(w, 404, "not_found", "project not found")
		return
	}
	s.streamSSE(w, r, "project:"+id.String())
}

func (s *Server) streamSSE(w http.ResponseWriter, r *http.Request, topic string) {
	if s.jobs == nil {
		writeErr(w, 503, "unavailable", "realtime unavailable")
		return
	}
	flusher, ok := w.(http.Flusher)
	if !ok {
		writeErr(w, 500, "internal", "streaming unsupported")
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache, no-transform")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Accel-Buffering", "no")
	w.WriteHeader(http.StatusOK)
	if rc := http.NewResponseController(w); rc != nil {
		_ = rc.SetWriteDeadline(time.Time{}) // flux long : pas de deadline d'écriture
	}

	ch, unsub := s.jobs.ListenHub(topic)
	defer unsub()

	writeEvent := func(event string, data string) bool {
		if _, err := fmt.Fprintf(w, "event: %s\ndata: %s\n\n", event, data); err != nil {
			return false
		}
		flusher.Flush()
		return true
	}

	if !writeEvent("ping", `{"ok":true}`) {
		return
	}

	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()
	notify := r.Context().Done()
	for {
		select {
		case <-notify:
			return
		case <-ticker.C:
			if !writeEvent("ping", `{"ok":true}`) {
				return
			}
		case msg, ok := <-ch:
			if !ok {
				return
			}
			var payload map[string]any
			event := "message"
			if json.Unmarshal(msg, &payload) == nil {
				if ev, _ := payload["event"].(string); ev != "" {
					event = ev
				}
			}
			if !writeEvent(event, string(msg)) {
				return
			}
		}
	}
}
