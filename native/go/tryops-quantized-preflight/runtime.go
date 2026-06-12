package main

import (
	"context"
	"encoding/json"
	"os/exec"
	"strings"
	"time"
)

var runtimePackages = []string{
	"torch",
	"transformers",
	"accelerate",
	"gptqmodel",
	"auto_gptq",
	"optimum",
	"awq",
	"autoawq",
	"vllm",
	"safetensors",
}

func inspectRuntime(ctx context.Context, python string) RuntimeInfo {
	info := RuntimeInfo{PythonExecutable: python, Packages: map[string]Package{}}
	for _, name := range runtimePackages {
		info.Packages[name] = Package{}
	}
	if path, err := exec.LookPath(python); err == nil {
		info.PythonExecutable = path
	}
	info.Packages = inspectPythonPackages(ctx, info.PythonExecutable)
	info.GPUs = inspectGPUs(ctx)
	return info
}

func inspectPythonPackages(ctx context.Context, python string) map[string]Package {
	packages := map[string]Package{}
	for _, name := range runtimePackages {
		packages[name] = Package{}
	}
	script := `
import importlib.metadata as md
import importlib.util
import json
names = """torch transformers accelerate gptqmodel auto_gptq optimum awq autoawq vllm safetensors""".split()
out = {}
for name in names:
    available = importlib.util.find_spec(name) is not None
    version = ""
    for candidate in (name.replace("_", "-"), name):
        try:
            version = md.version(candidate)
            break
        except Exception:
            pass
    out[name] = {"available": available, "version": version}
print(json.dumps(out, sort_keys=True))
`
	runCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	output, err := exec.CommandContext(runCtx, python, "-c", script).Output()
	if err != nil {
		return packages
	}
	_ = json.Unmarshal(output, &packages)
	return packages
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

func packageAvailable(runtime RuntimeInfo, name string) bool {
	pkg, ok := runtime.Packages[name]
	return ok && pkg.Available
}
