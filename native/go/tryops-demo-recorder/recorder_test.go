package main

import "testing"

func TestValidateStoryboardRequiresSevenSteps(t *testing.T) {
	board := storyboard{}
	for i := 0; i < 7; i++ {
		board.Steps = append(board.Steps, step{
			ID:              string(rune('a' + i)),
			Title:           "Step",
			PrimaryArtifact: "artifact.json",
			Transcript:      []string{"line"},
		})
	}
	if failures := validateStoryboard(board); len(failures) != 0 {
		t.Fatalf("unexpected failures: %#v", failures)
	}
	board.Steps = board.Steps[:6]
	if failures := validateStoryboard(board); len(failures) == 0 {
		t.Fatalf("expected missing step failure")
	}
}

func TestValueTextFormatsWholeNumbers(t *testing.T) {
	if got := valueText(float64(18)); got != "18" {
		t.Fatalf("valueText(float64 whole) = %q", got)
	}
	if got := valueText(float64(0.525)); got != "0.525" {
		t.Fatalf("valueText(float64 decimal) = %q", got)
	}
}

func TestBuildReportFailsWhenVideoMissing(t *testing.T) {
	cfg := config{
		Root:            "/tmp",
		StoryboardPath:  "/tmp/storyboard.json",
		VideoPath:       "/tmp/does-not-exist.mp4",
		SecondsPerFrame: 2,
		Width:           1280,
		Height:          720,
		FPS:             30,
	}
	board := storyboard{Steps: []step{{ID: "1"}, {ID: "2"}, {ID: "3"}, {ID: "4"}, {ID: "5"}, {ID: "6"}, {ID: "7"}}}
	report := buildReport(cfg, board, []frameSummary{{}, {}, {}, {}, {}, {}, {}, {}, {}}, encodeResult{ExitCode: 0}, nil)
	if report.Passed {
		t.Fatalf("report passed without a video")
	}
}
