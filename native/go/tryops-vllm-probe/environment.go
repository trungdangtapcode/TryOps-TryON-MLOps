package main

import (
	"context"
	"os/exec"
	"strings"
	"time"
)

func inspectEnvironment(ctx context.Context) EnvironmentInfo {
	env := EnvironmentInfo{}
	if path, err := exec.LookPath("vllm"); err == nil {
		env.VLLMBinaryAvailable = true
		env.VLLMBinaryPath = path
	}
	env.GPUs = inspectGPUs(ctx)
	return env
}

func inspectGPUs(ctx context.Context) []GPUInfo {
	if _, err := exec.LookPath("nvidia-smi"); err != nil {
		return []GPUInfo{{QuerySkipped: true, QueryError: "nvidia-smi not found"}}
	}
	gpuCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()
	output, err := exec.CommandContext(gpuCtx, "nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits").Output()
	if err != nil {
		return []GPUInfo{{QueryError: err.Error()}}
	}
	lines := strings.Split(strings.TrimSpace(string(output)), "\n")
	gpus := make([]GPUInfo, 0, len(lines))
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		parts := strings.Split(line, ",")
		gpu := GPUInfo{RawLine: line}
		if len(parts) > 0 {
			gpu.Name = strings.TrimSpace(parts[0])
		}
		if len(parts) > 1 {
			gpu.MemoryMiB = strings.TrimSpace(parts[1])
		}
		if len(parts) > 2 {
			gpu.Driver = strings.TrimSpace(parts[2])
		}
		gpus = append(gpus, gpu)
	}
	return gpus
}
