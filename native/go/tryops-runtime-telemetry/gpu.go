package main

import (
	"context"
	"os/exec"
	"strconv"
	"strings"
	"time"
)

func queryGPU(binary string) GPUTelemetry {
	resolved := binary
	if path, err := exec.LookPath(binary); err == nil {
		resolved = path
	} else if !strings.Contains(binary, "/") {
		return GPUTelemetry{Queried: true, Available: false, QueryError: "nvidia-smi not found"}
	}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	output, err := exec.CommandContext(
		ctx,
		resolved,
		"--query-gpu=index,name,memory.used,memory.total,utilization.gpu,power.draw",
		"--format=csv,noheader,nounits",
	).Output()
	if err != nil {
		return GPUTelemetry{Queried: true, Available: false, BinaryPath: resolved, QueryError: err.Error()}
	}
	devices := parseNvidiaSMI(string(output))
	return GPUTelemetry{
		Queried:    true,
		Available:  len(devices) > 0,
		BinaryPath: resolved,
		Devices:    devices,
	}
}

func parseNvidiaSMI(raw string) []GPUDevice {
	lines := strings.Split(strings.TrimSpace(raw), "\n")
	devices := make([]GPUDevice, 0, len(lines))
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		parts := strings.Split(line, ",")
		for index := range parts {
			parts[index] = strings.TrimSpace(parts[index])
		}
		if len(parts) < 6 {
			continue
		}
		usedMiB := parseNumber(parts[2])
		totalMiB := parseNumber(parts[3])
		device := GPUDevice{
			Index:              parts[0],
			Name:               parts[1],
			MemoryUsedMiB:      round6(usedMiB),
			MemoryTotalMiB:     round6(totalMiB),
			MemoryUsedGB:       round6(usedMiB / 1024.0),
			MemoryTotalGB:      round6(totalMiB / 1024.0),
			MemoryUtilization:  utilization(usedMiB, totalMiB),
			ComputeUtilization: round6(parseNumber(parts[4]) / 100.0),
			PowerDrawWatts:     round6(parseNumber(parts[5])),
		}
		devices = append(devices, device)
	}
	return devices
}

func parseNumber(raw string) float64 {
	clean := strings.TrimSpace(raw)
	clean = strings.TrimSuffix(clean, "%")
	value, err := strconv.ParseFloat(clean, 64)
	if err != nil {
		return 0
	}
	return value
}

func utilization(used float64, total float64) float64 {
	if total <= 0 {
		return 0
	}
	return round6(used / total)
}
