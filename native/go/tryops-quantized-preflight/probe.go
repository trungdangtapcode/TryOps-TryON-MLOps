package main

import (
	"context"
	"net/http"
	"sort"
	"strings"
	"time"
)

func runPreflight(ctx context.Context, cfg Config) Report {
	runtime := inspectRuntime(ctx, cfg.Python)
	report := Report{
		SchemaVersion: "tryops.quantized_model_preflight.v1",
		CreatedAt:     time.Now().UTC().Format(time.RFC3339Nano),
		Status:        "partial",
		Driver: DriverInfo{
			Name:     "tryops-quantized-preflight",
			Language: "go",
			Version:  "0.1.0",
		},
		Runtime: runtime,
		Research: map[string]string{
			"transformers_gptq": "https://huggingface.co/docs/transformers/main/quantization/gptq",
			"transformers_awq":  "https://huggingface.co/docs/transformers/main/quantization/awq",
			"gptq_paper":        "https://arxiv.org/abs/2210.17323",
			"awq_paper":         "https://arxiv.org/abs/2306.00978",
		},
	}
	client := clientWithTimeout(cfg.RequestTimeout)
	for _, candidate := range cfg.Candidates {
		report.Candidates = append(report.Candidates, inspectCandidate(ctx, client, cfg, runtime, candidate))
	}
	report.Summary = buildSummary(report.Candidates)
	report.Passed = report.Summary.TotalCandidates > 0 && report.Summary.SuitableCandidates == report.Summary.TotalCandidates && report.Summary.LoadReadyCandidates == report.Summary.TotalCandidates
	if report.Passed {
		report.Status = "passed"
		return report
	}
	if report.Summary.SuitableCandidates > 0 {
		report.Status = "partial"
		report.Reasons = append(report.Reasons, "suitable quantized model repositories were found, but local loader packages are missing for at least one method")
		return report
	}
	report.Status = "failed"
	report.Reasons = append(report.Reasons, "no suitable quantized model repository was verified")
	return report
}

func inspectCandidate(ctx context.Context, client *http.Client, cfg Config, runtime RuntimeInfo, spec CandidateSpec) CandidateResult {
	result := CandidateResult{Method: spec.Method, Repo: spec.Repo}
	config, statusCode, size, configURL, err := fetchConfig(ctx, client, cfg.BaseURL, spec.Repo)
	result.ConfigURL = configURL
	result.StatusCode = statusCode
	result.HTTPBytes = size
	if err != nil {
		result.Error = err.Error()
		result.Reasons = append(result.Reasons, "config fetch failed")
		return result
	}
	result.Reachable = true
	result.ModelType = config.ModelType
	result.Architecture = config.Architectures
	result.License = config.License
	result.Quantization = parseQuantization(config.QuantizationConfig)
	result.ArtifactChecks = []ArtifactCheck{
		headArtifact(ctx, client, cfg.BaseURL, spec.Repo, "model.safetensors"),
	}
	result.Suitable = isSuitable(spec.Method, result.Quantization)
	if !result.Suitable {
		result.Reasons = append(result.Reasons, "quantization_config does not match expected method/bits")
	}
	result.LoaderPackages, result.MissingPackages = loaderRequirements(spec.Method, runtime)
	result.LoadReady = result.Suitable && len(result.MissingPackages) == 0
	if !result.LoadReady {
		result.Reasons = append(result.Reasons, "local loader packages are incomplete")
	}
	return result
}

func parseQuantization(raw map[string]interface{}) QuantizationConfig {
	q := QuantizationConfig{}
	if raw == nil {
		return q
	}
	q.Method = lowerString(raw["quant_method"])
	q.Bits = intValue(raw["bits"])
	q.GroupSize = intValue(raw["group_size"])
	q.Version = stringValue(raw["version"])
	if value, ok := boolValue(raw["zero_point"]); ok {
		q.ZeroPoint = &value
	}
	if value, ok := boolValue(raw["sym"]); ok {
		q.Sym = &value
	}
	return q
}

func isSuitable(method string, quant QuantizationConfig) bool {
	method = strings.ToLower(method)
	return quant.Method == method && quant.Bits == 4 && quant.GroupSize > 0
}

func loaderRequirements(method string, runtime RuntimeInfo) ([]string, []string) {
	base := []string{"torch", "transformers", "accelerate", "safetensors"}
	alternatives := map[string][]string{
		"gptq": {"gptqmodel", "auto_gptq"},
		"awq":  {"awq", "autoawq"},
	}
	required := append([]string{}, base...)
	missing := []string{}
	for _, name := range base {
		if !packageAvailable(runtime, name) {
			missing = append(missing, name)
		}
	}
	alts := alternatives[strings.ToLower(method)]
	if len(alts) == 0 {
		return required, append(missing, "unknown_method_runtime")
	}
	altAvailable := false
	for _, name := range alts {
		required = append(required, name)
		if packageAvailable(runtime, name) {
			altAvailable = true
		}
	}
	if !altAvailable {
		missing = append(missing, strings.Join(alts, "|"))
	}
	return required, missing
}

func buildSummary(candidates []CandidateResult) Summary {
	summary := Summary{TotalCandidates: len(candidates), GPTQStatus: "missing", AWQStatus: "missing"}
	missingSet := map[string]bool{}
	for _, candidate := range candidates {
		if candidate.Suitable {
			summary.SuitableCandidates++
		}
		if candidate.LoadReady {
			summary.LoadReadyCandidates++
		}
		status := candidateStatus(candidate)
		switch strings.ToLower(candidate.Method) {
		case "gptq":
			summary.GPTQStatus = status
		case "awq":
			summary.AWQStatus = status
		}
		for _, item := range candidate.MissingPackages {
			missingSet[item] = true
		}
	}
	for item := range missingSet {
		summary.MissingPackages = append(summary.MissingPackages, item)
	}
	sort.Strings(summary.MissingPackages)
	return summary
}

func candidateStatus(candidate CandidateResult) string {
	if candidate.LoadReady {
		return "load_ready"
	}
	if candidate.Suitable {
		return "candidate_verified_runtime_missing"
	}
	if candidate.Reachable {
		return "unsuitable"
	}
	return "unreachable"
}
