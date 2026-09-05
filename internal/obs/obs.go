package obs

import (
	"log/slog"
	"os"
)

// Logger returns a JSON structured logger with service metadata.
func Logger(service string) *slog.Logger {
	return slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo})).
		With("service", service)
}

// JobAttrs standard attributes for job tracing.
func JobAttrs(jobID, projectID, orgID string) []any {
	return []any{"job_id", jobID, "project_id", projectID, "org_id", orgID}
}
