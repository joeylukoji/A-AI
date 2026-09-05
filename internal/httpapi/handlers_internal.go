package httpapi

import (
	"context"
	"crypto/subtle"
	"encoding/base64"
	"encoding/json"
	"net/http"
	"strings"

	"github.com/a-ai/a-ai/internal/artifact"
	"github.com/a-ai/a-ai/internal/jobs"
	"github.com/google/uuid"
)

// checkInternal authenticates worker->API calls. It uses a constant-time
// comparison so response timing can't leak how many leading bytes of the
// token an attacker guessed correctly, and it rejects an empty configured
// token outright so a misconfiguration can never be satisfied by an equally
// empty (or missing) header.
func (s *Server) checkInternal(r *http.Request) bool {
	want := s.cfg.InternalToken
	if want == "" {
		return false
	}
	got := r.Header.Get("X-Internal-Token")
	return subtle.ConstantTimeCompare([]byte(got), []byte(want)) == 1
}

func (s *Server) persistPreviewPNG(ctx context.Context, projectID uuid.UUID, b64, existingKey string) string {
	if existingKey != "" || b64 == "" || s.storage == nil {
		return existingKey
	}
	raw := b64
	if i := strings.Index(raw, ","); i >= 0 {
		raw = raw[i+1:]
	}
	png, err := base64.StdEncoding.DecodeString(raw)
	if err != nil || len(png) == 0 {
		return existingKey
	}
	key := s.storage.Key(projectID, "preview", "png")
	if err := s.storage.Put(ctx, key, "image/png", png); err != nil {
		return existingKey
	}
	return key
}

func (s *Server) handleInternalComplete(w http.ResponseWriter, r *http.Request) {
	if !s.checkInternal(r) {
		writeErr(w, 401, "unauthorized", "invalid internal token")
		return
	}
	id, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		writeErr(w, 404, "not_found", "job not found")
		return
	}
	var req jobs.CompleteRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeErr(w, 400, "invalid_json", "invalid body")
		return
	}
	if req.Status == "" {
		req.Status = "succeeded"
	}
	if err := s.jobs.Complete(r.Context(), id, req); err != nil {
		writeErr(w, 500, "internal", err.Error())
		return
	}
	writeJSON(w, 200, map[string]string{"ok": "true"})
}

func (s *Server) handleInternalRunning(w http.ResponseWriter, r *http.Request) {
	if !s.checkInternal(r) {
		writeErr(w, 401, "unauthorized", "invalid internal token")
		return
	}
	id, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		writeErr(w, 404, "not_found", "job not found")
		return
	}
	var body struct {
		Step string `json:"step"`
	}
	_ = json.NewDecoder(r.Body).Decode(&body)
	if err := s.jobs.MarkRunning(r.Context(), id, body.Step); err != nil {
		writeErr(w, 500, "internal", err.Error())
		return
	}
	writeJSON(w, 200, map[string]string{"ok": "true"})
}

func (s *Server) handleInternalSaveRevision(w http.ResponseWriter, r *http.Request) {
	if !s.checkInternal(r) {
		writeErr(w, 401, "unauthorized", "invalid internal token")
		return
	}
	projectID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		writeErr(w, 404, "not_found", "project not found")
		return
	}
	var body struct {
		UserID       string          `json:"user_id"`
		Source       string          `json:"source"`
		PlanDocument json.RawMessage `json:"plan_document"`
		BuildingSpec json.RawMessage `json:"building_spec"`
		PreviewKey   string          `json:"preview_key"`
		ImagePNGB64  string          `json:"image_png_b64"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeErr(w, 400, "invalid_json", "invalid body")
		return
	}
	userID, err := uuid.Parse(body.UserID)
	if err != nil {
		writeErr(w, 400, "invalid_user", "user_id required")
		return
	}
	if body.Source == "" {
		body.Source = "ai"
	}
	body.PreviewKey = s.persistPreviewPNG(r.Context(), projectID, body.ImagePNGB64, body.PreviewKey)
	rev, err := s.projects.SaveRevision(r.Context(), projectID, userID, body.Source, body.PlanDocument, body.BuildingSpec, body.PreviewKey, nil)
	if err != nil {
		writeErr(w, 500, "internal", err.Error())
		return
	}
	writeJSON(w, 200, rev)
}

func (s *Server) handleInternalCreateArtifact(w http.ResponseWriter, r *http.Request) {
	if !s.checkInternal(r) {
		writeErr(w, 401, "unauthorized", "invalid internal token")
		return
	}
	projectID, err := uuid.Parse(r.PathValue("id"))
	if err != nil {
		writeErr(w, 404, "not_found", "project not found")
		return
	}
	var body struct {
		JobID          string `json:"job_id"`
		RevisionID     string `json:"revision_id"`
		Kind           string `json:"kind"`
		StorageKey     string `json:"storage_key"`
		ContentType    string `json:"content_type"`
		ChecksumSHA256 string `json:"checksum_sha256"`
		Bytes          int64  `json:"bytes"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeErr(w, 400, "invalid_json", "invalid body")
		return
	}
	if body.Kind == "" || body.StorageKey == "" {
		writeErr(w, 400, "invalid", "kind and storage_key required")
		return
	}
	in := artifact.CreateInput{
		ProjectID:      projectID,
		Kind:           body.Kind,
		StorageKey:     body.StorageKey,
		ContentType:    body.ContentType,
		ChecksumSHA256: body.ChecksumSHA256,
		Bytes:          body.Bytes,
	}
	if body.JobID != "" {
		if id, err := uuid.Parse(body.JobID); err == nil {
			in.JobID = &id
		}
	}
	if body.RevisionID != "" {
		if id, err := uuid.Parse(body.RevisionID); err == nil {
			in.RevisionID = &id
		}
	}
	art, err := s.artifacts.Create(r.Context(), in)
	if err != nil {
		writeErr(w, 500, "internal", err.Error())
		return
	}
	writeJSON(w, 201, art)
}
