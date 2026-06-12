package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
)

func loadStoryboard(path string) (storyboard, error) {
	payload, err := os.ReadFile(path)
	if err != nil {
		return storyboard{}, err
	}
	var board storyboard
	if err := json.Unmarshal(payload, &board); err != nil {
		return storyboard{}, err
	}
	if failures := validateStoryboard(board); len(failures) > 0 {
		return storyboard{}, fmt.Errorf("invalid storyboard: %s", strings.Join(failures, "; "))
	}
	return board, nil
}

func validateStoryboard(board storyboard) []string {
	var failures []string
	if len(board.Steps) < 7 {
		failures = append(failures, "expected at least seven demo steps")
	}
	seen := map[string]bool{}
	for i, step := range board.Steps {
		if strings.TrimSpace(step.ID) == "" {
			failures = append(failures, fmt.Sprintf("step %d missing id", i+1))
		}
		if seen[step.ID] {
			failures = append(failures, fmt.Sprintf("duplicate step id %q", step.ID))
		}
		seen[step.ID] = true
		if strings.TrimSpace(step.Title) == "" {
			failures = append(failures, fmt.Sprintf("step %d missing title", i+1))
		}
		if strings.TrimSpace(step.PrimaryArtifact) == "" {
			failures = append(failures, fmt.Sprintf("step %s missing primary artifact", step.ID))
		}
		if len(step.Transcript) == 0 {
			failures = append(failures, fmt.Sprintf("step %s missing transcript", step.ID))
		}
	}
	return failures
}

func valueText(value interface{}) string {
	switch typed := value.(type) {
	case string:
		return typed
	case float64:
		if typed == float64(int64(typed)) {
			return fmt.Sprintf("%d", int64(typed))
		}
		return fmt.Sprintf("%.3f", typed)
	case bool:
		if typed {
			return "true"
		}
		return "false"
	default:
		return fmt.Sprintf("%v", typed)
	}
}
