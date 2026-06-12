package main

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

func renderMarkdown(report PerformanceBudgetReport) string {
	status := "FAIL"
	if report.Passed {
		status = "PASS"
	}
	var b strings.Builder
	fmt.Fprintf(&b, "# Native Performance Budget: %s\n\n", status)
	fmt.Fprintf(&b, "- Schema: `%s`\n", report.SchemaVersion)
	fmt.Fprintf(&b, "- Coverage: `%s`\n", report.CoverageLevel)
	fmt.Fprintf(&b, "- Budgets: %d passed / %d total\n", report.Summary.PassedBudgets, report.Summary.TotalBudgets)
	fmt.Fprintf(&b, "- CI artifact: `%s`\n\n", report.CI.ArtifactName)
	b.WriteString("## Inputs\n\n")
	b.WriteString("| Input | Present | Schema | Path |\n")
	b.WriteString("| --- | --- | --- | --- |\n")
	for _, input := range report.Inputs {
		fmt.Fprintf(&b, "| %s | %t | `%s` | `%s` |\n", input.Name, input.Present, input.SchemaVersion, input.Path)
	}
	b.WriteString("\n## Budgets\n\n")
	b.WriteString("| Status | Language | Budget | Key Measurement | Source |\n")
	b.WriteString("| --- | --- | --- | --- | --- |\n")
	for _, budget := range report.Budgets {
		rowStatus := "PASS"
		if !budget.Passed {
			rowStatus = "FAIL"
		}
		fmt.Fprintf(&b, "| %s | %s | `%s` | %s | `%s` |\n", rowStatus, budget.Language, budget.Name, keyMeasurement(budget), budget.SourceArtifact)
	}
	failures := failedBudgets(report.Budgets)
	if len(failures) > 0 {
		b.WriteString("\n## Failures\n\n")
		for _, budget := range failures {
			fmt.Fprintf(&b, "- `%s`: %s\n", budget.Name, strings.Join(budget.Failures, "; "))
		}
	}
	return b.String()
}

func writeMarkdown(path string, markdown string) error {
	if path == "" {
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, []byte(markdown), 0o644)
}

func keyMeasurement(budget BudgetResult) string {
	keys := make([]string, 0, len(budget.Measurements))
	for key := range budget.Measurements {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	preferred := []string{"p95_ms", "p99_ms", "requests_per_second", "throughput_ratio", "failed_rules", "failed_checks", "tokens_per_second_mean", "size_bytes"}
	used := map[string]bool{}
	parts := []string{}
	for _, key := range preferred {
		if _, ok := budget.Measurements[key]; ok {
			parts = append(parts, fmt.Sprintf("%s=%.3f", key, budget.Measurements[key]))
			used[key] = true
		}
		if len(parts) == 2 {
			return strings.Join(parts, "<br>")
		}
	}
	for _, key := range keys {
		if used[key] {
			continue
		}
		parts = append(parts, fmt.Sprintf("%s=%.3f", key, budget.Measurements[key]))
		if len(parts) == 2 {
			break
		}
	}
	if len(parts) == 0 {
		return ""
	}
	return strings.Join(parts, "<br>")
}

func failedBudgets(budgets []BudgetResult) []BudgetResult {
	out := []BudgetResult{}
	for _, budget := range budgets {
		if !budget.Passed {
			out = append(out, budget)
		}
	}
	return out
}
