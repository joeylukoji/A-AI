package export

import (
	"bytes"
	"context"
	_ "embed"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

var qcadHTTP = &http.Client{Timeout: 25 * time.Second}

//go:embed qcad_normalize.js
var qcadNormalizeJS string

func qcadBinary() string {
	if p := strings.TrimSpace(os.Getenv("QCAD_BIN")); p != "" {
		return p
	}
	if p, err := exec.LookPath("qcad"); err == nil {
		return p
	}
	if p, err := exec.LookPath("qcadcmd"); err == nil {
		return p
	}
	if runtime.GOOS == "windows" {
		for _, c := range []string{
			`C:\Program Files\QCAD\qcadcmd.exe`,
			`C:\Program Files\QCAD\qcad.exe`,
			`C:\Program Files (x86)\QCAD\qcadcmd.exe`,
		} {
			if _, err := os.Stat(c); err == nil {
				return c
			}
		}
	}
	return ""
}

func normalizeViaHTTP(base string, dxf []byte) ([]byte, bool) {
	url := strings.TrimRight(base, "/") + "/normalize"
	ctx, cancel := context.WithTimeout(context.Background(), 25*time.Second)
	defer cancel()
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(dxf))
	if err != nil {
		return nil, false
	}
	req.Header.Set("Content-Type", "application/dxf")
	resp, err := qcadHTTP.Do(req)
	if err != nil {
		return nil, false
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, false
	}
	out, err := io.ReadAll(io.LimitReader(resp.Body, 8<<20))
	if err != nil || len(out) < 16 {
		return nil, false
	}
	return out, true
}

func normalizeWithQCAD(dxf []byte) ([]byte, bool) {
	if u := strings.TrimSpace(os.Getenv("QCAD_URL")); u != "" {
		if out, ok := normalizeViaHTTP(u, dxf); ok {
			return out, true
		}
	}
	bin := qcadBinary()
	if bin == "" {
		return nil, false
	}
	dir, err := os.MkdirTemp("", "aai-qcad-*")
	if err != nil {
		return nil, false
	}
	defer os.RemoveAll(dir)

	inPath := filepath.Join(dir, "in.dxf")
	outPath := filepath.Join(dir, "out.dxf")
	scriptPath := filepath.Join(dir, "normalize.js")
	if err := os.WriteFile(inPath, dxf, 0o600); err != nil {
		return nil, false
	}
	if err := os.WriteFile(scriptPath, []byte(qcadNormalizeJS), 0o600); err != nil {
		return nil, false
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, bin,
		"-no-gui",
		"-allow-multiple-instances",
		"-autostart", scriptPath,
		"--", inPath, outPath,
	)
	cmd.Dir = dir
	if err := cmd.Run(); err != nil {
		return nil, false
	}
	out, err := os.ReadFile(outPath)
	if err != nil || len(out) < 16 {
		return nil, false
	}
	return out, true
}
