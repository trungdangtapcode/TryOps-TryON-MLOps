package main

import (
	"flag"
	"os"
	"path/filepath"
	"strings"
)

func parseConfig() Config {
	root := flag.String("root", getenv("TRYOPS_ROOT", "."), "repository root")
	compose := flag.String("compose", getenv("TRYOPS_COMPOSE_FILE", "docker-compose.yml"), "docker compose file")
	output := flag.String("output", getenv("TRYOPS_TLS_CONTRACT_OUTPUT", "artifacts/eval/tls/native_tls_contract.json"), "report output path")
	cert := flag.String("cert", getenv("TRYOPS_TLS_CERT_PATH", "artifacts/tls/tryops.local.crt"), "TLS certificate path")
	key := flag.String("key", getenv("TRYOPS_TLS_KEY_PATH", "artifacts/tls/tryops.local.key"), "TLS private key path")
	mode := flag.String("mode", getenv("TRYOPS_TLS_CONTRACT_MODE", "plan"), "plan or live")
	url := flag.String("url", getenv("TRYOPS_TLS_CONTRACT_URL", "https://127.0.0.1:18443/health"), "HTTPS health URL for live mode")
	flag.Parse()

	cfg := Config{
		Root:        filepath.Clean(*root),
		ComposePath: *compose,
		OutputPath:  *output,
		CertPath:    *cert,
		KeyPath:     *key,
		Mode:        strings.ToLower(strings.TrimSpace(*mode)),
		URL:         strings.TrimSpace(*url),
	}
	cfg.ComposePath = rootRelative(cfg.Root, cfg.ComposePath)
	cfg.OutputPath = rootRelative(cfg.Root, cfg.OutputPath)
	cfg.CertPath = rootRelative(cfg.Root, cfg.CertPath)
	cfg.KeyPath = rootRelative(cfg.Root, cfg.KeyPath)
	return cfg
}

func rootRelative(root string, path string) string {
	if filepath.IsAbs(path) {
		return filepath.Clean(path)
	}
	return filepath.Join(root, path)
}

func getenv(name string, fallback string) string {
	value := strings.TrimSpace(os.Getenv(name))
	if value == "" {
		return fallback
	}
	return value
}
