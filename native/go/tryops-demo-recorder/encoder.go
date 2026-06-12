package main

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

func encodeVideo(ctx context.Context, cfg config) (encodeResult, error) {
	if err := os.MkdirAll(filepath.Dir(cfg.VideoPath), 0o755); err != nil {
		return encodeResult{}, err
	}
	input := filepath.Join(cfg.FramesDir, "frame_%03d.png")
	args := []string{
		"-y",
		"-framerate", fmt.Sprintf("1/%d", cfg.SecondsPerFrame),
		"-i", input,
		"-vf", fmt.Sprintf("fps=%d,format=yuv420p", cfg.FPS),
		"-c:v", "libx264",
		"-movflags", "+faststart",
		cfg.VideoPath,
	}
	cmd := exec.CommandContext(ctx, cfg.FFmpegPath, args...)
	var output bytes.Buffer
	cmd.Stdout = &output
	cmd.Stderr = &output
	err := cmd.Run()
	result := encodeResult{
		Command:    append([]string{cfg.FFmpegPath}, args...),
		ExitCode:   exitCode(err),
		OutputTail: tailString(output.String(), 2500),
	}
	if ctx.Err() != nil {
		return result, ctx.Err()
	}
	if err != nil {
		return result, err
	}
	return result, nil
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

func tailString(value string, limit int) string {
	if limit <= 0 || len(value) <= limit {
		return strings.TrimSpace(value)
	}
	return strings.TrimSpace(value[len(value)-limit:])
}
