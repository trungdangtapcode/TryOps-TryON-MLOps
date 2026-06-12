package main

import (
	"context"
	"os"
	"path/filepath"
	"testing"
)

func TestEvaluateComposeTLSProfile(t *testing.T) {
	dir := t.TempDir()
	composePath := filepath.Join(dir, "docker-compose.yml")
	if err := os.WriteFile(composePath, []byte(`
services:
  gateway-tls:
    profiles: ["tls"]
    build:
      context: .
      dockerfile: Dockerfile.gateway
    environment:
      TRYOPS_GATEWAY_TLS_CERT_PATH: /run/secrets/tryops_tls_cert
      TRYOPS_GATEWAY_TLS_KEY_PATH: /run/secrets/tryops_tls_key
      TRYOPS_GATEWAY_HEALTH_ADDR: 127.0.0.1:8443
    ports:
      - "${TRYOPS_GATEWAY_TLS_PORT:-8443}:8443"
    secrets:
      - tryops_gateway_quota_postgres_dsn
      - tryops_tls_cert
      - tryops_tls_key
    healthcheck:
      test: ["CMD-SHELL", "TRYOPS_GATEWAY_HEALTH_SCHEME=https tryops-gateway health-check"]
secrets:
  tryops_gateway_quota_postgres_dsn:
    environment: TRYOPS_GATEWAY_QUOTA_POSTGRES_DSN
  tryops_tls_cert:
    environment: TRYOPS_TLS_CERT_PEM
  tryops_tls_key:
    environment: TRYOPS_TLS_KEY_PEM
`), 0o644); err != nil {
		t.Fatal(err)
	}
	var checks []Check
	summary := evaluateCompose(composePath, &checks)
	if !allPassed(checks) {
		t.Fatalf("expected compose checks to pass: %#v", checks)
	}
	if summary.Service != "gateway-tls" || summary.Profile != "tls" {
		t.Fatalf("unexpected summary: %#v", summary)
	}
}

func TestTLSVersionName(t *testing.T) {
	if got := tlsVersionName(0x0304); got != "TLS1.3" {
		t.Fatalf("unexpected TLS version name: %s", got)
	}
}

func TestEvaluateFailsWithoutCertificate(t *testing.T) {
	dir := t.TempDir()
	composePath := filepath.Join(dir, "docker-compose.yml")
	if err := os.WriteFile(composePath, []byte("services: {}\nsecrets: {}\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	report := evaluate(context.Background(), Config{
		Root:        dir,
		ComposePath: composePath,
		CertPath:    filepath.Join(dir, "missing.crt"),
		KeyPath:     filepath.Join(dir, "missing.key"),
		Mode:        "plan",
		URL:         "https://127.0.0.1:18443/health",
	})
	if report.Passed {
		t.Fatal("expected missing certificate and compose profile to fail")
	}
}
