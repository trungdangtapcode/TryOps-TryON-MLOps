package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestEvaluateSecretRotationContract(t *testing.T) {
	root := t.TempDir()
	writeFixture(t, root, "configs/secret_rotation_policy.json", `{
  "schema_version": "tryops.secret_rotation_policy.v1",
  "provider": {"type":"hashicorp_vault","kv_mount":"kv","kubernetes_auth_mount":"kubernetes","role":"tryops-runtime","external_secrets_store":"tryops-vault"},
  "workload_identity": {"service_account":"tryops-runtime","namespace":"tryops","projected_token_audience":"vault","projected_token_expiration_seconds":3600,"spiffe_id":"spiffe://tryops.local/ns/tryops/sa/tryops-runtime"},
  "api_key_registry": {"path":"configs/api_keys.json","storage":"hash_only","rotation_days":90,"overlap_days":7,"break_glass_key_count_max":1},
  "managed_secrets": [
    {"name":"tryops_postgres_password","env":"TRYOPS_POSTGRES_PASSWORD","compose_secret":"tryops_postgres_password","vault_path":"kv/data/tryops/postgres","vault_property":"password","rotation_days":30,"owner":"platform"},
    {"name":"tryops_minio_root_user","env":"TRYOPS_MINIO_ROOT_USER","compose_secret":"tryops_minio_root_user","vault_path":"kv/data/tryops/minio","vault_property":"root_user","rotation_days":90,"owner":"platform"},
    {"name":"tryops_minio_root_password","env":"TRYOPS_MINIO_ROOT_PASSWORD","compose_secret":"tryops_minio_root_password","vault_path":"kv/data/tryops/minio","vault_property":"root_password","rotation_days":30,"owner":"platform"},
    {"name":"tryops_gateway_quota_postgres_dsn","env":"TRYOPS_GATEWAY_QUOTA_POSTGRES_DSN","compose_secret":"tryops_gateway_quota_postgres_dsn","vault_path":"kv/data/tryops/gateway","vault_property":"quota_postgres_dsn","rotation_days":30,"owner":"platform"},
    {"name":"tryops_webhook_secret","env":"TRYOPS_WEBHOOK_SECRET","compose_secret":"","vault_path":"kv/data/tryops/controller","vault_property":"registry_webhook_secret","rotation_days":30,"owner":"mlops"},
    {"name":"tryops_github_webhook_secret","env":"TRYOPS_GITHUB_WEBHOOK_SECRET","compose_secret":"","vault_path":"kv/data/tryops/controller","vault_property":"github_webhook_secret","rotation_days":30,"owner":"mlops"},
    {"name":"tryops_tls_cert","env":"TRYOPS_TLS_CERT_PEM","compose_secret":"tryops_tls_cert","vault_path":"kv/data/tryops/tls","vault_property":"cert_pem","rotation_days":90,"owner":"platform"},
    {"name":"tryops_tls_key","env":"TRYOPS_TLS_KEY_PEM","compose_secret":"tryops_tls_key","vault_path":"kv/data/tryops/tls","vault_property":"key_pem","rotation_days":90,"owner":"platform"}
  ],
  "required_manifests": ["infra/kubernetes/secret-management/vault-secretstore.yaml","infra/kubernetes/secret-management/tryops-external-secrets.yaml"]
}`)
	writeFixture(t, root, "configs/api_keys.json", `{"schema_version":"tryops.api_keys.v1","keys":[
{"key_id":"admin","role":"admin","key_hash_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","scopes":["admin:read"],"active":true},
{"key_id":"operator","role":"operator","key_hash_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","scopes":["promotion:evaluate"],"active":true},
{"key_id":"viewer","role":"viewer","key_hash_sha256":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","scopes":["session:read"],"active":true}
]}`)
	writeFixture(t, root, ".env.example", "TRYOPS_POSTGRES_PASSWORD=\nTRYOPS_MINIO_ROOT_USER=\nTRYOPS_MINIO_ROOT_PASSWORD=\nTRYOPS_GATEWAY_QUOTA_POSTGRES_DSN=\nTRYOPS_WEBHOOK_SECRET=\nTRYOPS_GITHUB_WEBHOOK_SECRET=\nTRYOPS_TLS_CERT_PEM=\nTRYOPS_TLS_KEY_PEM=\n")
	writeFixture(t, root, "docker-compose.yml", `services:
  gateway:
    secrets: [tryops_gateway_quota_postgres_dsn]
  gateway-tls:
    secrets: [tryops_gateway_quota_postgres_dsn, tryops_tls_cert, tryops_tls_key]
secrets:
  tryops_postgres_password:
    environment: TRYOPS_POSTGRES_PASSWORD
  tryops_minio_root_user:
    environment: TRYOPS_MINIO_ROOT_USER
  tryops_minio_root_password:
    environment: TRYOPS_MINIO_ROOT_PASSWORD
  tryops_gateway_quota_postgres_dsn:
    environment: TRYOPS_GATEWAY_QUOTA_POSTGRES_DSN
  tryops_tls_cert:
    environment: TRYOPS_TLS_CERT_PEM
  tryops_tls_key:
    environment: TRYOPS_TLS_KEY_PEM
`)
	writeFixture(t, root, "infra/kubernetes/secret-management/vault-secretstore.yaml", vaultStoreFixture())
	writeFixture(t, root, "infra/kubernetes/secret-management/tryops-external-secrets.yaml", externalSecretFixture())
	cfg := Config{RootPath: root, PolicyPath: "configs/secret_rotation_policy.json", ComposePath: "docker-compose.yml", EnvExamplePath: ".env.example", OutputPath: "artifacts/eval/secrets/native_secret_rotation_contract.json"}

	report, err := evaluate(cfg)
	if err != nil {
		t.Fatal(err)
	}
	if !report.Passed || report.Summary.FailedChecks != 0 {
		t.Fatalf("expected passing report: %#v", report.Checks)
	}
	if report.ProductionReady {
		t.Fatal("plan-mode contract should not be production ready without live env")
	}
	if report.Summary.ManagedSecrets != 8 || report.Summary.ExternalSecrets != 8 || report.Summary.ComposeSecrets != 6 {
		t.Fatalf("unexpected summary: %#v", report.Summary)
	}
	if !report.WorkloadIdentity.ProjectedTokenManifest || !report.APIKeyRegistry.HashOnly {
		t.Fatalf("missing identity/hash evidence: %#v", report)
	}
}

func TestRegistryRejectsInvalidHash(t *testing.T) {
	policy := Policy{APIKeyRegistry: APIKeyPolicy{Path: "configs/api_keys.json", Storage: "hash_only", RotationDays: 90, OverlapDays: 7}}
	registry := APIKeyRegistry{SchemaVersion: "tryops.api_keys.v1", Keys: []APIKeyEntry{{KeyID: "bad", Role: "admin", KeyHashSHA256: "raw-secret", Active: true}}}
	checks, summary := validateAPIKeyRegistry(policy, registry)
	if summary.HashOnly {
		t.Fatal("expected invalid hash to fail")
	}
	if allPassed(checks) {
		t.Fatalf("expected failed check: %#v", checks)
	}
}

func TestEvaluateLiveVaultExercise(t *testing.T) {
	root := t.TempDir()
	writeFixture(t, root, "token", "root-token\n")
	server := newFakeVault(t)
	defer server.Close()

	policy := Policy{
		Provider: ProviderPolicy{Type: "hashicorp_vault", KVMount: "kv", KubernetesAuthMount: "kubernetes", Role: "tryops-runtime"},
		ManagedSecrets: []ManagedSecret{
			{Name: "db", Env: "DB_PASSWORD", VaultPath: "kv/data/tryops/postgres", VaultProperty: "password", RotationDays: 30, Owner: "platform"},
			{Name: "minio_user", Env: "MINIO_USER", VaultPath: "kv/data/tryops/minio", VaultProperty: "root_user", RotationDays: 90, Owner: "platform"},
			{Name: "minio_password", Env: "MINIO_PASSWORD", VaultPath: "kv/data/tryops/minio", VaultProperty: "root_password", RotationDays: 30, Owner: "platform"},
		},
	}
	secrets := []SecretSummary{
		{Name: "db", VaultPath: "kv/data/tryops/postgres", VaultProperty: "password"},
		{Name: "minio_user", VaultPath: "kv/data/tryops/minio", VaultProperty: "root_user"},
		{Name: "minio_password", VaultPath: "kv/data/tryops/minio", VaultProperty: "root_password"},
	}
	cfg := Config{
		RootPath:           root,
		LiveVault:          true,
		VaultAddr:          server.URL,
		WorkloadTokenPath:  "token",
		LiveSecretPrefix:   "tryops/live-secret-rotation",
		LiveTimeoutSeconds: 2,
	}

	checks, live := exerciseLiveVault(cfg, policy, secrets)
	if !allPassed(checks) {
		t.Fatalf("expected live checks to pass: %#v", checks)
	}
	if !live.LiveExercisePassed || live.KVPathsExercised != 2 || live.SecretPropertiesRotated != 3 {
		t.Fatalf("unexpected live summary: %#v", live)
	}
	if live.MinVersionObserved != 1 || live.MaxVersionObserved != 2 || live.AuthSource != "workload_identity_token_path" {
		t.Fatalf("unexpected live version/auth evidence: %#v", live)
	}
	body, _ := json.Marshal(live)
	if strings.Contains(string(body), "root-token") || strings.Contains(string(body), "tryops-live-") {
		t.Fatalf("live report leaked secret material: %s", string(body))
	}
}

func writeFixture(t *testing.T, root string, path string, body string) {
	t.Helper()
	full := filepath.Join(root, path)
	if err := os.MkdirAll(filepath.Dir(full), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(full, []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
}

func allPassed(checks []Check) bool {
	for _, check := range checks {
		if !check.Passed {
			return false
		}
	}
	return true
}

func newFakeVault(t *testing.T) *httptest.Server {
	t.Helper()
	mounts := map[string]bool{}
	type versionedSecret struct {
		version int
		data    map[string]string
	}
	secrets := map[string]versionedSecret{}
	mux := http.NewServeMux()
	mux.HandleFunc("/v1/sys/health", func(w http.ResponseWriter, r *http.Request) {
		writeJSONResponse(t, w, map[string]interface{}{"initialized": true, "sealed": false, "standby": false, "version": "fake-vault"})
	})
	mux.HandleFunc("/v1/sys/mounts", func(w http.ResponseWriter, r *http.Request) {
		data := map[string]interface{}{}
		for mount := range mounts {
			data[mount+"/"] = map[string]interface{}{"type": "kv"}
		}
		writeJSONResponse(t, w, map[string]interface{}{"data": data})
	})
	mux.HandleFunc("/v1/sys/mounts/kv", func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("X-Vault-Token") == "" {
			http.Error(w, "missing token", http.StatusForbidden)
			return
		}
		mounts["kv"] = true
		w.WriteHeader(http.StatusNoContent)
	})
	mux.HandleFunc("/v1/kv/data/", func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("X-Vault-Token") == "" {
			http.Error(w, "missing token", http.StatusForbidden)
			return
		}
		switch r.Method {
		case http.MethodPost:
			var payload struct {
				Data map[string]string `json:"data"`
			}
			if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
				http.Error(w, err.Error(), http.StatusBadRequest)
				return
			}
			item := secrets[r.URL.Path]
			item.version++
			item.data = payload.Data
			secrets[r.URL.Path] = item
			writeJSONResponse(t, w, map[string]interface{}{"data": map[string]interface{}{"version": item.version}})
		case http.MethodGet:
			item, ok := secrets[r.URL.Path]
			if !ok {
				http.NotFound(w, r)
				return
			}
			writeJSONResponse(t, w, map[string]interface{}{
				"data": map[string]interface{}{
					"data":     item.data,
					"metadata": map[string]interface{}{"version": item.version},
				},
			})
		default:
			w.WriteHeader(http.StatusMethodNotAllowed)
		}
	})
	return httptest.NewServer(mux)
}

func writeJSONResponse(t *testing.T, w http.ResponseWriter, body interface{}) {
	t.Helper()
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(body); err != nil {
		t.Fatal(err)
	}
}

func vaultStoreFixture() string {
	return `apiVersion: v1
kind: ServiceAccount
metadata:
  name: tryops-runtime
  namespace: tryops
automountServiceAccountToken: false
---
apiVersion: external-secrets.io/v1
kind: SecretStore
metadata:
  name: tryops-vault
  namespace: tryops
spec:
  provider:
    vault:
      path: kv
      auth:
        kubernetes:
          mountPath: kubernetes
          role: tryops-runtime
          serviceAccountRef:
            name: tryops-runtime
`
}

func externalSecretFixture() string {
	return `apiVersion: external-secrets.io/v1
kind: ExternalSecret
spec:
  data:
    - secretKey: TRYOPS_POSTGRES_PASSWORD
    - secretKey: TRYOPS_MINIO_ROOT_USER
    - secretKey: TRYOPS_MINIO_ROOT_PASSWORD
    - secretKey: TRYOPS_GATEWAY_QUOTA_POSTGRES_DSN
    - secretKey: TRYOPS_WEBHOOK_SECRET
    - secretKey: TRYOPS_GITHUB_WEBHOOK_SECRET
    - secretKey: TRYOPS_TLS_CERT_PEM
    - secretKey: TRYOPS_TLS_KEY_PEM
---
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      serviceAccountName: tryops-runtime
      automountServiceAccountToken: false
      volumes:
        - name: vault-identity-token
          projected:
            sources:
              - serviceAccountToken:
                  audience: vault
                  expirationSeconds: 3600
                  path: token
`
}
