package main

import (
	"sort"
	"strings"
)

var criticalPythonPackages = []string{
	"fastapi",
	"uvicorn",
	"pydantic",
	"mlflow",
	"dvc",
	"torch",
	"transformers",
	"accelerate",
	"bitsandbytes",
	"diffusers",
	"vllm",
}

func validatePython(cfg Config) (PythonSummary, []Check) {
	checks := []Check{}
	declared := []string{}
	locked := map[string]string{}
	hashCount := 0

	pyproject, err := readText(cfg.RootPath, cfg.PyprojectPath)
	checks = append(checks, check("python.pyproject.present", err == nil, cfg.PyprojectPath))
	if err == nil {
		declared = parsePyprojectDependencies(pyproject)
		checks = append(checks, check("python.pyproject.dependencies_declared", len(declared) >= 9, formatCount(len(declared))))
	}

	uvLock, err := readText(cfg.RootPath, cfg.UVLockPath)
	checks = append(checks, check("python.uv_lock.present", err == nil, cfg.UVLockPath))
	if err == nil {
		locked, hashCount = parseUVLock(uvLock)
		checks = append(checks, check("python.uv_lock.has_packages", len(locked) > len(declared), formatCount(len(locked))))
		checks = append(checks, check("python.uv_lock.has_hashes", hashCount >= len(locked), formatCount(hashCount)))
	}

	missing := []string{}
	for _, dep := range declared {
		if _, ok := locked[dep]; !ok {
			missing = append(missing, dep)
		}
	}
	checks = append(checks, check("python.all_declared_dependencies_locked", len(missing) == 0 && len(declared) > 0, strings.Join(missing, ",")))

	critical := make([]PythonPackage, 0, len(criticalPythonPackages))
	for _, name := range criticalPythonPackages {
		version := locked[name]
		critical = append(critical, PythonPackage{Name: name, Version: version})
		checks = append(checks, check("python.critical."+name+".locked", version != "", version))
	}
	checks = append(checks, check("python.accelerate_bitsandbytes_drift_locked", locked["accelerate"] != "" && locked["bitsandbytes"] != "", "accelerate="+locked["accelerate"]+" bitsandbytes="+locked["bitsandbytes"]))

	return PythonSummary{
		PyprojectPath:       cfg.PyprojectPath,
		LockPath:            cfg.UVLockPath,
		DeclaredCount:       len(declared),
		LockedPackageCount:  len(locked),
		HashCount:           hashCount,
		CriticalPackages:    critical,
		MissingDeclarations: missing,
	}, checks
}

func parsePyprojectDependencies(text string) []string {
	seen := map[string]bool{}
	deps := []string{}
	inList := false
	for _, raw := range strings.Split(text, "\n") {
		line := strings.TrimSpace(raw)
		if strings.HasPrefix(line, "#") || line == "" {
			continue
		}
		if strings.Contains(line, "= [") {
			inList = true
			continue
		}
		if inList && strings.HasPrefix(line, "]") {
			inList = false
			continue
		}
		if !inList {
			continue
		}
		value := quotedValue(line)
		if value == "" {
			continue
		}
		name := normalizePackageName(value)
		if name == "" || seen[name] {
			continue
		}
		seen[name] = true
		deps = append(deps, name)
	}
	sort.Strings(deps)
	return deps
}

func parseUVLock(text string) (map[string]string, int) {
	packages := map[string]string{}
	hashCount := strings.Count(text, "hash = \"sha256:")
	currentName := ""
	for _, raw := range strings.Split(text, "\n") {
		line := strings.TrimSpace(raw)
		if line == "[[package]]" {
			currentName = ""
			continue
		}
		if strings.HasPrefix(line, "name = ") {
			currentName = normalizePackageName(quotedValue(line))
			continue
		}
		if currentName != "" && strings.HasPrefix(line, "version = ") {
			packages[currentName] = quotedValue(line)
		}
	}
	return packages, hashCount
}

func normalizePackageName(value string) string {
	value = strings.TrimSpace(strings.ToLower(value))
	if cut := strings.IndexAny(value, "[<>=~!; "); cut >= 0 {
		value = value[:cut]
	}
	value = strings.ReplaceAll(value, "_", "-")
	return strings.Trim(value, ",\"'")
}
