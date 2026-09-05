package artifact

import (
	"context"
	"database/sql"
	"errors"

	"github.com/a-ai/a-ai/internal/domain"
	"github.com/google/uuid"
)

var ErrNotFound = errors.New("artifact not found")

type Service struct {
	db *sql.DB
}

func NewService(db *sql.DB) *Service {
	return &Service{db: db}
}

type CreateInput struct {
	ProjectID      uuid.UUID
	RevisionID     *uuid.UUID
	JobID          *uuid.UUID
	Kind           string
	StorageKey     string
	ContentType    string
	ChecksumSHA256 string
	Bytes          int64
}

func (s *Service) Create(ctx context.Context, in CreateInput) (*domain.Artifact, error) {
	var a domain.Artifact
	err := s.db.QueryRowContext(ctx, `
		INSERT INTO artifacts (project_id, revision_id, job_id, kind, storage_key, content_type, checksum_sha256, bytes)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
		RETURNING id, project_id, revision_id, job_id, kind, storage_key, content_type, COALESCE(checksum_sha256,''), bytes, created_at
	`, in.ProjectID, in.RevisionID, in.JobID, in.Kind, in.StorageKey, in.ContentType, in.ChecksumSHA256, in.Bytes).Scan(
		&a.ID, &a.ProjectID, &a.RevisionID, &a.JobID, &a.Kind, &a.StorageKey, &a.ContentType, &a.ChecksumSHA256, &a.Bytes, &a.CreatedAt,
	)
	return &a, err
}

func (s *Service) Get(ctx context.Context, id uuid.UUID) (*domain.Artifact, error) {
	var a domain.Artifact
	err := s.db.QueryRowContext(ctx, `
		SELECT id, project_id, revision_id, job_id, kind, storage_key, content_type, COALESCE(checksum_sha256,''), bytes, created_at
		FROM artifacts WHERE id=$1
	`, id).Scan(
		&a.ID, &a.ProjectID, &a.RevisionID, &a.JobID, &a.Kind, &a.StorageKey, &a.ContentType, &a.ChecksumSHA256, &a.Bytes, &a.CreatedAt,
	)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	return &a, err
}

func (s *Service) ListByProject(ctx context.Context, projectID uuid.UUID, kind string) ([]domain.Artifact, error) {
	var (
		rows *sql.Rows
		err  error
	)
	if kind == "" {
		rows, err = s.db.QueryContext(ctx, `
			SELECT id, project_id, revision_id, job_id, kind, storage_key, content_type, COALESCE(checksum_sha256,''), bytes, created_at
			FROM artifacts WHERE project_id=$1 ORDER BY created_at DESC
		`, projectID)
	} else {
		rows, err = s.db.QueryContext(ctx, `
			SELECT id, project_id, revision_id, job_id, kind, storage_key, content_type, COALESCE(checksum_sha256,''), bytes, created_at
			FROM artifacts WHERE project_id=$1 AND kind=$2 ORDER BY created_at DESC
		`, projectID, kind)
	}
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []domain.Artifact
	for rows.Next() {
		var a domain.Artifact
		if err := rows.Scan(&a.ID, &a.ProjectID, &a.RevisionID, &a.JobID, &a.Kind, &a.StorageKey, &a.ContentType, &a.ChecksumSHA256, &a.Bytes, &a.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, a)
	}
	return out, rows.Err()
}
