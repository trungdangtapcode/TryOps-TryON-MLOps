package main

import (
	"bytes"
	"context"
	"errors"
	"os"
	"os/exec"
	"strings"
	"time"
)

func buildCommandSpecs(cfg config) []commandSpec {
	var specs []commandSpec
	if cfg.RunGate {
		specs = append(specs, commandSpec{
			Name:              "validate_bad_candidate_blocked",
			Args:              []string{"python", "scripts/validate_candidate.py", "samples/candidates/vton_candidate_bad.json", "--stage", "champion"},
			ExpectedExitCodes: []int{2},
			WantContains:      []string{`"approved": false`, "critical vulnerabilities", "candidate artifact is not signed"},
		})
	}
	if cfg.RefreshEvidence {
		specs = append(specs,
			makeSpec("refresh_pipeline_sample", "pipeline-sample"),
			makeSpec("refresh_vton_compare_sample", "vton-compare-sample"),
			makeSpec("refresh_rollback_sample", "rollback-sample"),
			makeSpec("refresh_llm_pareto_sample", "llm-pareto-sample"),
			makeSpec("refresh_energy_sample", "energy-sample"),
			makeSpec("refresh_governance_sample", "governance-sample"),
		)
	}
	if cfg.RefreshStack {
		specs = append(specs, makeSpec("refresh_full_stack_smoke", "app-smoke"))
	}
	return specs
}

func makeSpec(name string, target string) commandSpec {
	return commandSpec{
		Name:              name,
		Args:              []string{"make", target},
		ExpectedExitCodes: []int{0},
		WantContains:      []string{},
	}
}

func runCommands(ctx context.Context, cfg config, specs []commandSpec) []commandResult {
	results := make([]commandResult, 0, len(specs))
	for _, spec := range specs {
		results = append(results, runCommand(ctx, cfg, spec))
	}
	return results
}

func runCommand(ctx context.Context, cfg config, spec commandSpec) commandResult {
	started := time.Now()
	result := commandResult{
		Name:              spec.Name,
		Command:           spec.Args,
		ExitCode:          -1,
		ExpectedExitCodes: spec.ExpectedExitCodes,
	}
	if len(spec.Args) == 0 {
		result.Error = "empty command"
		result.DurationMS = time.Since(started).Milliseconds()
		return result
	}

	command := exec.CommandContext(ctx, spec.Args[0], spec.Args[1:]...)
	command.Dir = cfg.Root
	command.Env = commandEnv(os.Environ())
	var output bytes.Buffer
	command.Stdout = &output
	command.Stderr = &output
	err := command.Run()
	result.DurationMS = time.Since(started).Milliseconds()
	result.OutputTail = tailString(output.String(), 4000)
	result.ExitCode = exitCode(err)
	if err != nil && result.ExitCode < 0 {
		result.Error = err.Error()
	}
	if ctx.Err() != nil {
		result.Error = ctx.Err().Error()
		return result
	}

	if !containsExitCode(result.ExitCode, spec.ExpectedExitCodes) {
		result.Error = "unexpected exit code"
		return result
	}
	result.Missing = missingSubstrings(output.String(), spec.WantContains)
	if len(result.Missing) > 0 {
		result.Error = "command output missing expected content"
		return result
	}
	result.Passed = true
	return result
}

func commandEnv(base []string) []string {
	env := append([]string{}, base...)
	for i, item := range env {
		if strings.HasPrefix(item, "PYTHONPATH=") {
			env[i] = "PYTHONPATH=src"
			return env
		}
	}
	return append(env, "PYTHONPATH=src")
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

func containsExitCode(code int, expected []int) bool {
	if len(expected) == 0 {
		return code == 0
	}
	for _, item := range expected {
		if code == item {
			return true
		}
	}
	return false
}

func missingSubstrings(body string, expected []string) []string {
	var missing []string
	for _, item := range expected {
		if !strings.Contains(body, item) {
			missing = append(missing, item)
		}
	}
	return missing
}

func tailString(value string, limit int) string {
	if limit <= 0 || len(value) <= limit {
		return value
	}
	return value[len(value)-limit:]
}
