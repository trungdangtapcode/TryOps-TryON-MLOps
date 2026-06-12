package main

import (
	"encoding/json"
	"errors"
	"os"
)

func loadArtifacts(cfg Config) (ArtifactSet, error) {
	benchmark, benchmarkInput, err := loadArtifact[BenchmarkReport](cfg.Root, cfg.BenchmarkPath, "gateway_benchmark")
	if err != nil {
		return ArtifactSet{}, err
	}
	sloGate, sloInput, err := loadArtifact[SLOGateReport](cfg.Root, cfg.SLOGatePath, "slo_gate")
	if err != nil {
		return ArtifactSet{}, err
	}
	perfStats, perfInput, err := loadArtifact[PerfStatsReport](cfg.Root, cfg.PerfStatsPath, "perf_stats")
	if err != nil {
		return ArtifactSet{}, err
	}
	configContract, configInput, err := loadArtifact[ConfigContractReport](cfg.Root, cfg.ConfigContractPath, "config_contract")
	if err != nil {
		return ArtifactSet{}, err
	}
	return ArtifactSet{
		Benchmark:      benchmark,
		SLOGate:        sloGate,
		PerfStats:      perfStats,
		ConfigContract: configContract,
		Inputs:         []InputArtifact{benchmarkInput, sloInput, perfInput, configInput},
	}, nil
}

func loadArtifact[T any](root string, path string, name string) (T, InputArtifact, error) {
	var out T
	fullPath := resolvePath(root, path)
	input := InputArtifact{Name: name, Path: relPath(root, fullPath)}
	info, err := os.Stat(fullPath)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			input.Present = false
			input.Error = "missing"
			return out, input, nil
		}
		return out, input, err
	}
	input.Present = true
	input.Bytes = info.Size()
	payload, err := os.ReadFile(fullPath)
	if err != nil {
		return out, input, err
	}
	if err := json.Unmarshal(payload, &out); err != nil {
		input.Error = err.Error()
		return out, input, nil
	}
	var generic map[string]interface{}
	if err := json.Unmarshal(payload, &generic); err == nil {
		if value, ok := generic["schema_version"].(string); ok {
			input.SchemaVersion = value
		}
		if value, ok := generic["generated_at"].(string); ok {
			input.CreatedAt = value
		}
		if input.CreatedAt == "" {
			if value, ok := generic["created_at"].(string); ok {
				input.CreatedAt = value
			}
		}
	}
	return out, input, nil
}

func inputByName(inputs []InputArtifact, name string) InputArtifact {
	for _, input := range inputs {
		if input.Name == name {
			return input
		}
	}
	return InputArtifact{Name: name}
}
