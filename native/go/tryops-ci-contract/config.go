package main

import (
	"flag"
	"os"
	"path/filepath"
)

func parseConfig() Config {
	var cfg Config
	flag.StringVar(&cfg.RootPath, "root", getenv("TRYOPS_CI_CONTRACT_ROOT", "."), "repository root")
	flag.StringVar(&cfg.WorkflowPath, "workflow", getenv("TRYOPS_CI_CONTRACT_WORKFLOW", ".github/workflows/ci.yml"), "GitHub Actions workflow path")
	flag.StringVar(&cfg.MakefilePath, "makefile", getenv("TRYOPS_CI_CONTRACT_MAKEFILE", "Makefile"), "Makefile path")
	flag.StringVar(&cfg.VulnerabilityPath, "vulnerability", getenv("TRYOPS_CI_CONTRACT_VULN", "artifacts/eval/security/vulnerability_scan_report.json"), "vulnerability report path")
	flag.StringVar(&cfg.SupplyChainPath, "supply-chain", getenv("TRYOPS_CI_CONTRACT_SUPPLY", "artifacts/eval/supply_chain/supply_chain_report.json"), "supply-chain report path")
	flag.StringVar(&cfg.ContainerReportPath, "container", getenv("TRYOPS_CI_CONTRACT_CONTAINER", "artifacts/eval/containers/native_container_contract_report.json"), "container contract report path")
	flag.StringVar(&cfg.OutputPath, "output", getenv("TRYOPS_CI_CONTRACT_OUTPUT", "artifacts/eval/ci/native_ci_contract.json"), "JSON report output path")
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

func rootJoin(root string, path string) string {
	if filepath.IsAbs(path) {
		return path
	}
	return filepath.Join(root, path)
}
