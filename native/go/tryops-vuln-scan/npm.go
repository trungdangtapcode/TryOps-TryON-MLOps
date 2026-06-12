package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"time"
)

func runNPMAudit(ctx context.Context, cfg config) scanResult {
	started := time.Now()
	result := scanResult{
		Name:          "web_npm_audit",
		Tool:          "npm",
		Path:          "web",
		ExitCode:      -1,
		RawOutputPath: relativePath(cfg.Root, cfg.NPMAuditOutput),
	}
	command := exec.CommandContext(ctx, "npm", "audit", "--json")
	command.Dir = filepath.Join(cfg.Root, "web")
	var output bytes.Buffer
	command.Stdout = &output
	command.Stderr = &output
	err := command.Run()
	result.DurationMS = time.Since(started).Milliseconds()
	result.ExitCode = exitCode(err)
	if writeErr := writeRawJSON(cfg.NPMAuditOutput, output.Bytes()); writeErr != nil {
		result.Error = writeErr.Error()
		return result
	}
	vulns, parseErr := parseNPMAudit(output.Bytes())
	if parseErr != nil {
		result.Error = parseErr.Error()
		return result
	}
	result.Vulnerabilities = vulns
	if err != nil && result.ExitCode < 0 {
		result.Error = err.Error()
		return result
	}
	if vulns["high"] > 0 || vulns["critical"] > 0 {
		result.Error = "npm audit found high or critical vulnerabilities"
		return result
	}
	if result.ExitCode != 0 && vulns["total"] > 0 {
		result.Error = "npm audit found vulnerabilities"
		return result
	}
	result.Passed = true
	return result
}

func writeRawJSON(path string, payload []byte) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	if len(bytes.TrimSpace(payload)) == 0 {
		payload = []byte(`{"error":"empty npm audit output"}`)
	}
	return os.WriteFile(path, append(bytes.TrimRight(payload, "\n"), '\n'), 0o644)
}

func parseNPMAudit(payload []byte) (map[string]int, error) {
	var parsed struct {
		Metadata struct {
			Vulnerabilities map[string]int `json:"vulnerabilities"`
		} `json:"metadata"`
	}
	if err := json.Unmarshal(payload, &parsed); err != nil {
		return nil, err
	}
	if parsed.Metadata.Vulnerabilities == nil {
		return nil, errors.New("npm audit output missing metadata.vulnerabilities")
	}
	return parsed.Metadata.Vulnerabilities, nil
}

func exitCode(err error) int {
	if err == nil {
		return 0
	}
	var exitErr *exec.ExitError
	if errors.As(err, &exitErr) {
		return exitErr.ExitCode()
	}
	return -1
}
