package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

func buildReport(cfg config, board storyboard, frames []frameSummary, encoder encodeResult, encodeErr error) videoReport {
	info, statErr := os.Stat(cfg.VideoPath)
	videoBytes := int64(0)
	if statErr == nil {
		videoBytes = info.Size()
	}
	hash := ""
	if videoBytes > 0 {
		hash = fileSHA256(cfg.VideoPath)
	}
	checks := []reportCheck{
		{Name: "storyboard_has_steps", Passed: len(board.Steps) >= 7, Detail: fmt.Sprintf("%d steps", len(board.Steps))},
		{Name: "frames_rendered", Passed: len(frames) >= len(board.Steps)+2, Detail: fmt.Sprintf("%d frames", len(frames))},
		{Name: "ffmpeg_encode", Passed: encodeErr == nil && encoder.ExitCode == 0, Detail: encoder.OutputTail},
		{Name: "video_written", Passed: videoBytes > 0, Detail: fmt.Sprintf("%d bytes", videoBytes)},
	}
	passed := true
	for _, check := range checks {
		if !check.Passed {
			passed = false
		}
	}
	return videoReport{
		SchemaVersion:   "tryops.professor_demo_video.v1",
		GeneratedAt:     time.Now().UTC().Format(time.RFC3339),
		Passed:          passed,
		StoryboardPath:  relPath(cfg.Root, cfg.StoryboardPath),
		VideoPath:       relPath(cfg.Root, cfg.VideoPath),
		VideoBytes:      videoBytes,
		VideoSHA256:     hash,
		FrameCount:      len(frames),
		StepCount:       len(board.Steps),
		DurationSeconds: len(frames) * cfg.SecondsPerFrame,
		Width:           cfg.Width,
		Height:          cfg.Height,
		FPS:             cfg.FPS,
		Frames:          frames,
		Encoder:         encoder,
		Checks:          checks,
	}
}

func fileSHA256(path string) string {
	payload, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	sum := sha256.Sum256(payload)
	return hex.EncodeToString(sum[:])
}

func writeReport(path string, report videoReport) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	payload, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(payload, '\n'), 0o644)
}
