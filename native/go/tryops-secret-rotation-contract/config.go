package main

import (
	"flag"
	"os"
)

func parseConfig() Config {
	cfg := Config{}
	flag.StringVar(&cfg.RootPath, "root", ".", "repository root")
	flag.StringVar(&cfg.PolicyPath, "policy", "configs/secret_rotation_policy.json", "secret rotation policy path")
	flag.StringVar(&cfg.ComposePath, "compose", "docker-compose.yml", "Compose file path")
	flag.StringVar(&cfg.EnvExamplePath, "env-example", ".env.example", "env example path")
	flag.StringVar(&cfg.OutputPath, "output", "artifacts/eval/secrets/native_secret_rotation_contract.json", "JSON evidence output path")
	flag.BoolVar(&cfg.LiveVault, "live-vault", envBool("TRYOPS_SECRET_ROTATION_LIVE_VAULT", false), "exercise live Vault KV v2 write/read/rotation")
	flag.StringVar(&cfg.VaultAddr, "vault-addr", os.Getenv("VAULT_ADDR"), "Vault base URL for live mode")
	flag.StringVar(&cfg.VaultToken, "vault-token", os.Getenv("VAULT_TOKEN"), "Vault token for live mode; token file is preferred when configured")
	flag.StringVar(&cfg.WorkloadTokenPath, "token-path", os.Getenv("TRYOPS_WORKLOAD_IDENTITY_TOKEN_PATH"), "workload identity token file for live mode")
	flag.StringVar(&cfg.LiveSecretPrefix, "live-secret-prefix", "tryops/live-secret-rotation", "Vault KV path prefix for live smoke secrets")
	flag.IntVar(&cfg.LiveTimeoutSeconds, "live-timeout-seconds", 20, "Vault live-mode timeout in seconds")
	flag.Parse()
	return cfg
}

func envBool(name string, fallback bool) bool {
	switch os.Getenv(name) {
	case "1", "true", "TRUE", "yes", "YES", "on", "ON":
		return true
	case "0", "false", "FALSE", "no", "NO", "off", "OFF":
		return false
	default:
		return fallback
	}
}
