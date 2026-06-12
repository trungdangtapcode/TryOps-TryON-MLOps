package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestConfigContractPassesCompleteCompose(t *testing.T) {
	root := writeFixtureRoot(t, composeFixture())
	compose, err := loadCompose(filepath.Join(root, "docker-compose.yml"))
	if err != nil {
		t.Fatal(err)
	}

	report := evaluateContracts(Config{Root: root, ComposePath: filepath.Join(root, "docker-compose.yml")}, compose)

	if !report.Passed {
		t.Fatalf("expected contract to pass, failed checks: %+v", failedChecks(report.Checks))
	}
}

func TestConfigContractFailsWhenGatewayQuotaEnvIsMissing(t *testing.T) {
	root := writeFixtureRoot(t, strings.ReplaceAll(
		composeFixture(),
		"      TRYOPS_GATEWAY_QUOTA_VALKEY_ADDR: valkey:6379\n",
		"",
	))
	compose, err := loadCompose(filepath.Join(root, "docker-compose.yml"))
	if err != nil {
		t.Fatal(err)
	}

	report := evaluateContracts(Config{Root: root, ComposePath: filepath.Join(root, "docker-compose.yml")}, compose)

	if report.Passed {
		t.Fatalf("expected contract to fail")
	}
	if !hasFailedCheck(report.Checks, "service.gateway.env.TRYOPS_GATEWAY_QUOTA_VALKEY_ADDR") {
		t.Fatalf("missing expected failed check: %+v", failedChecks(report.Checks))
	}
}

func TestConfigContractFailsOnDirectCredentialEnv(t *testing.T) {
	root := writeFixtureRoot(t, strings.ReplaceAll(
		composeFixture(),
		"      POSTGRES_PASSWORD_FILE: /run/secrets/tryops_postgres_password\n",
		"      POSTGRES_PASSWORD: tryops\n",
	))
	compose, err := loadCompose(filepath.Join(root, "docker-compose.yml"))
	if err != nil {
		t.Fatal(err)
	}

	report := evaluateContracts(Config{Root: root, ComposePath: filepath.Join(root, "docker-compose.yml")}, compose)

	if report.Passed {
		t.Fatalf("expected contract to fail")
	}
	if !hasFailedCheck(report.Checks, "service.postgres.env.POSTGRES_PASSWORD.direct_secret_absent") {
		t.Fatalf("missing expected failed check: %+v", failedChecks(report.Checks))
	}
}

func TestConfigContractFailsWhenEnvExampleIsMissingSecret(t *testing.T) {
	root := writeFixtureRoot(t, composeFixture())
	envPath := filepath.Join(root, ".env.example")
	body, err := os.ReadFile(envPath)
	if err != nil {
		t.Fatal(err)
	}
	mustWrite(t, envPath, strings.ReplaceAll(string(body), "TRYOPS_GATEWAY_QUOTA_POSTGRES_DSN=host=postgres port=5432 user=tryops password=change-me-postgres-password dbname=tryops\n", ""))
	compose, err := loadCompose(filepath.Join(root, "docker-compose.yml"))
	if err != nil {
		t.Fatal(err)
	}

	report := evaluateContracts(Config{Root: root, ComposePath: filepath.Join(root, "docker-compose.yml")}, compose)

	if report.Passed {
		t.Fatalf("expected contract to fail")
	}
	if !hasFailedCheck(report.Checks, "env_example.var.TRYOPS_GATEWAY_QUOTA_POSTGRES_DSN") {
		t.Fatalf("missing expected failed check: %+v", failedChecks(report.Checks))
	}
}

func TestComposeParserAcceptsListDependsOn(t *testing.T) {
	root := writeFixtureRoot(t, composeFixture())
	compose, err := loadCompose(filepath.Join(root, "docker-compose.yml"))
	if err != nil {
		t.Fatal(err)
	}

	if got := compose.Services["api"].DependsOn["mlflow"]; got != "service_started" {
		t.Fatalf("api mlflow dependency = %q", got)
	}
	if got := compose.Services["gateway"].DependsOn["postgres"]; got != "service_healthy" {
		t.Fatalf("gateway postgres dependency = %q", got)
	}
}

func writeFixtureRoot(t *testing.T, compose string) string {
	t.Helper()
	root := t.TempDir()
	mustWrite(t, filepath.Join(root, "docker-compose.yml"), compose)
	mustWrite(t, filepath.Join(root, ".env.example"), envExampleFixture())
	mustWrite(t, filepath.Join(root, ".gitignore"), ".env\n")
	mustWrite(t, filepath.Join(root, "Dockerfile.gateway"), strings.Join(gatewaySourceEnvVars(), "\n"))
	mustWrite(
		t,
		filepath.Join(root, "native", "rust", "tryops-gateway", "src", "env.rs"),
		strings.Join(gatewaySourceEnvVars(), "\n"),
	)
	return root
}

func mustWrite(t *testing.T, path string, body string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
}

func failedChecks(checks []contractCheck) []contractCheck {
	failed := make([]contractCheck, 0)
	for _, check := range checks {
		if !check.Passed {
			failed = append(failed, check)
		}
	}
	return failed
}

func hasFailedCheck(checks []contractCheck, name string) bool {
	for _, check := range checks {
		if check.Name == name && !check.Passed {
			return true
		}
	}
	return false
}

func composeFixture() string {
	return `services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: tryops
      POSTGRES_PASSWORD_FILE: /run/secrets/tryops_postgres_password
      POSTGRES_DB: tryops
    secrets:
      - tryops_postgres_password
    ports:
      - "${TRYOPS_POSTGRES_PORT:-5432}:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
  valkey:
    image: valkey/valkey:8-alpine
    ports:
      - "${TRYOPS_VALKEY_PORT:-16379}:6379"
    healthcheck:
      test: ["CMD", "valkey-cli", "ping"]
  minio:
    image: minio/minio:latest
    environment:
      MINIO_ROOT_USER_FILE: /run/secrets/tryops_minio_root_user
      MINIO_ROOT_PASSWORD_FILE: /run/secrets/tryops_minio_root_password
    secrets:
      - tryops_minio_root_user
      - tryops_minio_root_password
    ports:
      - "${TRYOPS_MINIO_PORT:-9000}:9000"
      - "${TRYOPS_MINIO_CONSOLE_PORT:-9001}:9001"
  mlflow:
    build: .
    environment:
      TRYOPS_POSTGRES_USER: tryops
      TRYOPS_POSTGRES_DB: tryops
      MLFLOW_S3_ENDPOINT_URL: http://minio:9000
    secrets:
      - tryops_postgres_password
      - tryops_minio_root_user
      - tryops_minio_root_password
    ports:
      - "${TRYOPS_MLFLOW_PORT:-5000}:5000"
    depends_on:
      postgres:
        condition: service_healthy
      minio:
        condition: service_started
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "${TRYOPS_PROMETHEUS_PORT:-9090}:9090"
    depends_on:
      otel-collector:
        condition: service_started
      alertmanager:
        condition: service_started
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
  alertmanager:
    image: prom/alertmanager:latest
    ports:
      - "${TRYOPS_ALERTMANAGER_PORT:-9093}:9093"
    healthcheck:
      test: ["CMD", "amtool", "check-config", "/etc/alertmanager/alertmanager.yml"]
  grafana:
    image: grafana/grafana-oss:latest
    ports:
      - "${TRYOPS_GRAFANA_PORT:-3000}:3000"
  guardrail:
    build: .
    environment:
      TRYOPS_GUARDRAIL_ADDR: ":18083"
    ports:
      - "${TRYOPS_GUARDRAIL_PORT:-18083}:18083"
  api:
    build: .
    environment:
      TRYOPS_ENV: local
      MLFLOW_TRACKING_URI: http://mlflow:5000
      TRYOPS_GUARDRAIL_URL: http://guardrail:18083/v1/guardrails/evaluate
    ports:
      - "${TRYOPS_API_PORT:-8080}:8080"
    healthcheck:
      test: ["CMD", "python", "-c", "print('ok')"]
    depends_on:
      - mlflow
      - guardrail
  gateway:
    build: .
    environment:
      TRYOPS_GATEWAY_ADDR: 0.0.0.0:8081
      TRYOPS_GATEWAY_UPSTREAM: http://api:8080
      TRYOPS_GATEWAY_GUARDRAIL_URL: http://guardrail:18083/v1/guardrails/evaluate
      TRYOPS_GATEWAY_STATIC_DIR: /opt/tryops/web
      TRYOPS_GATEWAY_API_KEYS_PATH: /opt/tryops/configs/api_keys.json
      TRYOPS_GATEWAY_MAX_BODY_BYTES: "4194304"
      TRYOPS_GATEWAY_RATE_LIMIT_PER_MINUTE: "600"
      TRYOPS_GATEWAY_QUOTA_POSTGRES_DSN_FILE: /run/secrets/tryops_gateway_quota_postgres_dsn
      TRYOPS_GATEWAY_QUOTA_VALKEY_ADDR: valkey:6379
      TRYOPS_GATEWAY_QUOTA_VALKEY_PREFIX: tryops
      TRYOPS_GATEWAY_HEALTH_ADDR: 127.0.0.1:8081
    secrets:
      - tryops_gateway_quota_postgres_dsn
    ports:
      - "${TRYOPS_GATEWAY_PORT:-8081}:8081"
    healthcheck:
      test: ["CMD", "tryops-gateway", "health-check"]
    depends_on:
      postgres:
        condition: service_healthy
      valkey:
        condition: service_healthy
      guardrail:
        condition: service_started
      api:
        condition: service_healthy
volumes:
  alertmanager-data:
  postgres-data:
  valkey-data:
  minio-data:
  grafana-data:
secrets:
  tryops_postgres_password:
    environment: TRYOPS_POSTGRES_PASSWORD
  tryops_minio_root_user:
    environment: TRYOPS_MINIO_ROOT_USER
  tryops_minio_root_password:
    environment: TRYOPS_MINIO_ROOT_PASSWORD
  tryops_gateway_quota_postgres_dsn:
    environment: TRYOPS_GATEWAY_QUOTA_POSTGRES_DSN
`
}

func envExampleFixture() string {
	return `TRYOPS_POSTGRES_USER=tryops
TRYOPS_POSTGRES_DB=tryops
TRYOPS_POSTGRES_PASSWORD=change-me-postgres-password
TRYOPS_MINIO_ROOT_USER=tryops
TRYOPS_MINIO_ROOT_PASSWORD=change-me-minio-root-password
TRYOPS_GATEWAY_QUOTA_POSTGRES_DSN=host=postgres port=5432 user=tryops password=change-me-postgres-password dbname=tryops
TRYOPS_WEBHOOK_SECRET=change-me-webhook
TRYOPS_GITHUB_WEBHOOK_SECRET=change-me-github-webhook
ANTHROPIC_API_KEY=
`
}
