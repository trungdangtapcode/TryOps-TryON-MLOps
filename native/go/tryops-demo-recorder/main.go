package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
)

func main() {
	cfg := parseConfig()
	ctx, cancel := context.WithTimeout(context.Background(), cfg.Timeout)
	defer cancel()

	board, err := loadStoryboard(cfg.StoryboardPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "load storyboard: %v\n", err)
		os.Exit(2)
	}
	frames, err := renderStoryboard(cfg, board)
	if err != nil {
		fmt.Fprintf(os.Stderr, "render frames: %v\n", err)
		os.Exit(2)
	}
	encoder, encodeErr := encodeVideo(ctx, cfg)
	report := buildReport(cfg, board, frames, encoder, encodeErr)
	if err := writeReport(cfg.OutputPath, report); err != nil {
		fmt.Fprintf(os.Stderr, "write report: %v\n", err)
		os.Exit(2)
	}
	encoded, _ := json.Marshal(report)
	fmt.Println(string(encoded))
	if !report.Passed {
		os.Exit(1)
	}
	fmt.Printf("PASS professor demo video %s frames=%d duration=%ds\n", report.VideoPath, report.FrameCount, report.DurationSeconds)
}
