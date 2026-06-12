package main

import (
	"flag"
	"os"
	"path/filepath"
)

func parseConfig() Config {
	cfg := Config{}
	flag.StringVar(&cfg.RootPath, "root", getenv("TRYOPS_ROOT", "."), "repository root")
	flag.StringVar(&cfg.OutputPath, "output", getenv("TRYOPS_LIVE_SUPPLY_CHAIN_OUTPUT", "artifacts/eval/ci/live_supply_chain_report.json"), "JSON evidence output path")
	flag.StringVar(&cfg.SyftSBOMPath, "syft-sbom", "artifacts/eval/ci/syft/filesystem.spdx.json", "Syft SPDX JSON output path")
	flag.StringVar(&cfg.SyftVersionPath, "syft-version", "artifacts/eval/ci/syft/version.txt", "Syft version output path")
	flag.StringVar(&cfg.TrivyReportPath, "trivy-report", "artifacts/eval/ci/trivy/filesystem.json", "Trivy JSON output path")
	flag.StringVar(&cfg.TrivyVersionPath, "trivy-version", "artifacts/eval/ci/trivy/version.txt", "Trivy version output path")
	flag.StringVar(&cfg.CosignVersionPath, "cosign-version", "artifacts/eval/ci/cosign/version.txt", "Cosign version output path")
	flag.StringVar(&cfg.CosignPublicKey, "cosign-public-key", "artifacts/eval/ci/cosign/tryops-local.pub", "Cosign public key path")
	flag.StringVar(&cfg.CosignSignature, "cosign-signature", "artifacts/eval/ci/cosign/sbom.spdx.json.sig", "Cosign signature path")
	flag.StringVar(&cfg.CosignVerifyPath, "cosign-verify-output", "artifacts/eval/ci/cosign/verify-blob.txt", "Cosign verify output path")
	flag.StringVar(&cfg.SignedBlobPath, "signed-blob", "artifacts/eval/ci/syft/filesystem.spdx.json", "blob signed by Cosign")
	flag.StringVar(&cfg.SyftImage, "syft-image", getenv("TRYOPS_SYFT_IMAGE", "anchore/syft:v1.45.1"), "Syft container image used")
	flag.StringVar(&cfg.TrivyImage, "trivy-image", getenv("TRYOPS_TRIVY_IMAGE", "aquasec/trivy:0.71.0"), "Trivy container image used")
	flag.StringVar(&cfg.CosignImage, "cosign-image", getenv("TRYOPS_COSIGN_IMAGE", "ghcr.io/sigstore/cosign/cosign:v2.4.1"), "Cosign container image used")
	flag.Parse()
	cfg.RootPath = filepath.Clean(cfg.RootPath)
	return cfg
}

func getenv(name string, fallback string) string {
	if value := os.Getenv(name); value != "" {
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
