package storage

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"net/url"
	"path"
	"strings"
	"time"

	"github.com/a-ai/a-ai/internal/config"
	"github.com/google/uuid"
	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

// Client wraps MinIO / S3-compatible storage.
type Client struct {
	mc     *minio.Client
	bucket string
}

func New(cfg config.Config) (*Client, error) {
	endpoint := cfg.S3Endpoint
	secure := false
	if strings.HasPrefix(endpoint, "http://") || strings.HasPrefix(endpoint, "https://") {
		u, err := url.Parse(endpoint)
		if err != nil {
			return nil, fmt.Errorf("s3 endpoint: %w", err)
		}
		secure = u.Scheme == "https"
		endpoint = u.Host
	}
	mc, err := minio.New(endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(cfg.S3AccessKey, cfg.S3SecretKey, ""),
		Secure: secure,
	})
	if err != nil {
		return nil, err
	}
	c := &Client{mc: mc, bucket: cfg.S3Bucket}
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	exists, err := mc.BucketExists(ctx, cfg.S3Bucket)
	if err == nil && !exists {
		_ = mc.MakeBucket(ctx, cfg.S3Bucket, minio.MakeBucketOptions{})
	}
	return c, nil
}

func (c *Client) Put(ctx context.Context, key string, contentType string, data []byte) error {
	_, err := c.mc.PutObject(ctx, c.bucket, key, bytes.NewReader(data), int64(len(data)), minio.PutObjectOptions{
		ContentType: contentType,
	})
	return err
}

func (c *Client) Get(ctx context.Context, key string) ([]byte, string, error) {
	obj, err := c.mc.GetObject(ctx, c.bucket, key, minio.GetObjectOptions{})
	if err != nil {
		return nil, "", err
	}
	defer obj.Close()
	info, err := obj.Stat()
	if err != nil {
		return nil, "", err
	}
	b, err := io.ReadAll(obj)
	if err != nil {
		return nil, "", err
	}
	ct := info.ContentType
	if ct == "" {
		ct = "application/octet-stream"
	}
	return b, ct, nil
}

// Key builds a storage object key scoped to a single project. kind and ext
// are always literals supplied by call sites in this codebase today, never
// raw user input — but the sanitization below keeps it that way structurally:
// neither can contain a path separator or ".." traversal sequence, so no
// future caller can accidentally (or maliciously, via a compromised upstream)
// make a key escape "projects/<project-id>/".
func (c *Client) Key(projectID uuid.UUID, kind, ext string) string {
	kind = sanitizeKeySegment(kind)
	ext = sanitizeKeySegment(ext)
	return path.Join("projects", projectID.String(), fmt.Sprintf("%s-%s.%s", kind, uuid.NewString()[:8], ext))
}

// sanitizeKeySegment neutralizes path separators and traversal sequences in a
// single key component.
func sanitizeKeySegment(s string) string {
	s = strings.ReplaceAll(s, `\`, "_")
	s = strings.ReplaceAll(s, "/", "_")
	s = strings.ReplaceAll(s, "..", "_")
	if s == "" {
		return "x"
	}
	return s
}
