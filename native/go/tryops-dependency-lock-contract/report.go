package main

import (
	"fmt"
	"strings"
	"time"
)

func evaluate(cfg Config) (Report, error) {
	checks := []Check{}
	python, pythonChecks := validatePython(cfg)
	checks = append(checks, pythonChecks...)
	node, nodeChecks := validateNode(cfg)
	checks = append(checks, nodeChecks...)
	rust, rustChecks := validateRust(cfg)
	checks = append(checks, rustChecks...)
	goModules, goChecks := validateGoModules(cfg)
	checks = append(checks, goChecks...)
	makeChecks := validateMakefile(cfg)
	checks = append(checks, makeChecks...)

	passedChecks, failedChecks := countChecks(checks)
	passed := failedChecks == 0
	summary := summarize(passedChecks, failedChecks, checks, python, node, rust, goModules)
	return Report{
		SchemaVersion:   schemaVersion,
		GeneratedAt:     time.Now().UTC().Format(time.RFC3339),
		Passed:          passed,
		ProductionReady: passed,
		CoverageLevel:   "native_dependency_lock_contract",
		Python:          python,
		Node:            node,
		Rust:            rust,
		GoModules:       goModules,
		Checks:          checks,
		Evidence: []EvidenceRef{
			{Name: "uv_lock", Path: cfg.UVLockPath, Status: status(fileExists(cfg.RootPath, cfg.UVLockPath)), Detail: "cross-platform Python dependency lock"},
			{Name: "node_package_lock", Path: cfg.PackageLockPath, Status: status(fileExists(cfg.RootPath, cfg.PackageLockPath)), Detail: "Console exact dependency tree"},
			{Name: "rust_cargo_lock", Path: cfg.CargoLockPath, Status: status(fileExists(cfg.RootPath, cfg.CargoLockPath)), Detail: "Rust gateway exact crate resolution"},
			{Name: "go_module_checksums", Path: cfg.GoRootPath, Status: status(summary.GoExternalModules == summary.GoChecksumCoverage), Detail: fmt.Sprintf("%d/%d modules with external deps covered", summary.GoChecksumCoverage, summary.GoExternalModules)},
		},
		Research: researchRefs(),
		Notes: []string{
			"uv.lock was generated from pyproject.toml and pins accelerate/bitsandbytes versions without installing model packages.",
			"Go modules with no external requirements are allowed to omit go.sum; modules with external requirements must carry checksum coverage.",
		},
		Summary: summary,
	}, nil
}

func validateMakefile(cfg Config) []Check {
	text, err := readText(cfg.RootPath, cfg.MakefilePath)
	checks := []Check{check("makefile.present", err == nil, cfg.MakefilePath)}
	if err != nil {
		return checks
	}
	required := []string{
		"native-dependency-lock-contract-build:",
		"native-dependency-lock-contract-test:",
		"native-dependency-lock-contract-sample:",
		"native-dependency-lock-contract-sample",
		"native/go/tryops-dependency-lock-contract",
	}
	for _, item := range required {
		checks = append(checks, check("makefile.contains."+sanitizeName(item), strings.Contains(text, item), item))
	}
	return checks
}

func summarize(passedChecks int, failedChecks int, checks []Check, python PythonSummary, node NodeSummary, rust RustSummary, goModules []GoModuleSummary) Summary {
	external := 0
	covered := 0
	for _, module := range goModules {
		if len(module.Requires) == 0 {
			continue
		}
		external++
		if module.ChecksumCoverage {
			covered++
		}
	}
	return Summary{
		PassedChecks:       passedChecks,
		FailedChecks:       failedChecks,
		TotalChecks:        len(checks),
		PythonLocked:       python.LockedPackageCount,
		NodeLocked:         node.LockedPackageCount,
		RustLocked:         rust.LockedPackageCount,
		GoModules:          len(goModules),
		GoExternalModules:  external,
		GoChecksumCoverage: covered,
	}
}

func countChecks(checks []Check) (int, int) {
	passed := 0
	failed := 0
	for _, check := range checks {
		if check.Passed {
			passed++
		} else {
			failed++
		}
	}
	return passed, failed
}

func check(name string, passed bool, detail string) Check {
	return Check{Name: name, Passed: passed, Detail: detail}
}

func status(ok bool) string {
	if ok {
		return "passed"
	}
	return "failed"
}

func formatCount(count int) string {
	return fmt.Sprintf("%d", count)
}

func sanitizeName(value string) string {
	value = strings.TrimSuffix(value, ":")
	replacer := strings.NewReplacer("/", "_", "-", "_", ".", "_", ":", "", " ", "_")
	return replacer.Replace(value)
}

func researchRefs() []ResearchRef {
	return []ResearchRef{
		{Name: "uv locking and syncing", URL: "https://docs.astral.sh/uv/concepts/projects/sync/", Use: "Python dependency resolution into uv.lock"},
		{Name: "uv pip compile", URL: "https://docs.astral.sh/uv/pip/compile/", Use: "pyproject.toml dependency locking guidance"},
		{Name: "npm package-lock.json", URL: "https://docs.npmjs.com/cli/v8/configuring-npm/package-lock-json/", Use: "exact Console dependency tree committed to source"},
		{Name: "npm ci", URL: "https://docs.npmjs.com/cli/v8/commands/npm-ci", Use: "CI install from package-lock.json"},
		{Name: "Cargo.toml vs Cargo.lock", URL: "https://doc.rust-lang.org/cargo/guide/cargo-toml-vs-cargo-lock.html", Use: "Rust binary exact dependency resolution"},
		{Name: "Go modules reference", URL: "https://go.dev/ref/mod", Use: "Go module requirements and checksum authentication"},
	}
}
