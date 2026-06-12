package main

import (
	"flag"
	"os"
	"path/filepath"
)

func parseConfig() Config {
	cfg := Config{}
	flag.StringVar(&cfg.RootPath, "root", getenv("TRYOPS_DEP_LOCK_ROOT", "."), "repository root")
	flag.StringVar(&cfg.PyprojectPath, "pyproject", getenv("TRYOPS_DEP_LOCK_PYPROJECT", "pyproject.toml"), "Python pyproject path")
	flag.StringVar(&cfg.UVLockPath, "uv-lock", getenv("TRYOPS_DEP_LOCK_UV", "uv.lock"), "uv lockfile path")
	flag.StringVar(&cfg.PackageJSONPath, "package-json", getenv("TRYOPS_DEP_LOCK_PACKAGE_JSON", "web/package.json"), "package.json path")
	flag.StringVar(&cfg.PackageLockPath, "package-lock", getenv("TRYOPS_DEP_LOCK_PACKAGE_LOCK", "web/package-lock.json"), "package-lock.json path")
	flag.StringVar(&cfg.CargoTomlPath, "cargo-toml", getenv("TRYOPS_DEP_LOCK_CARGO_TOML", "native/rust/tryops-gateway/Cargo.toml"), "Cargo.toml path")
	flag.StringVar(&cfg.CargoLockPath, "cargo-lock", getenv("TRYOPS_DEP_LOCK_CARGO_LOCK", "native/rust/tryops-gateway/Cargo.lock"), "Cargo.lock path")
	flag.StringVar(&cfg.GoRootPath, "go-root", getenv("TRYOPS_DEP_LOCK_GO_ROOT", "native/go"), "native Go module root")
	flag.StringVar(&cfg.MakefilePath, "makefile", getenv("TRYOPS_DEP_LOCK_MAKEFILE", "Makefile"), "Makefile path")
	flag.StringVar(&cfg.OutputPath, "output", getenv("TRYOPS_DEP_LOCK_OUTPUT", "artifacts/eval/dependencies/native_dependency_lock_contract.json"), "JSON report output path")
	flag.Parse()
	cfg.RootPath = filepath.Clean(cfg.RootPath)
	return cfg
}

func getenv(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
