package main

import (
	"os"
	"time"
)

func evaluate(cfg Config) (Report, error) {
	policy, err := readJSON[Policy](cfg.RootPath, cfg.PolicyPath)
	if err != nil {
		return Report{}, err
	}
	registry, err := readJSON[APIKeyRegistry](cfg.RootPath, policy.APIKeyRegistry.Path)
	if err != nil {
		return Report{}, err
	}
	compose, err := readYAML[ComposeFile](cfg.RootPath, cfg.ComposePath)
	if err != nil {
		return Report{}, err
	}
	envExample, err := readText(cfg.RootPath, cfg.EnvExamplePath)
	if err != nil {
		return Report{}, err
	}
	checks := []Check{}
	checks = append(checks, validatePolicy(policy)...)
	registryChecks, registrySummary := validateAPIKeyRegistry(policy, registry)
	checks = append(checks, registryChecks...)
	composeChecks, composePresent := validateCompose(policy, compose, envExample)
	checks = append(checks, composeChecks...)
	kubeChecks, kubeSummary := validateKubernetes(cfg.RootPath, policy)
	checks = append(checks, kubeChecks...)

	secrets := summarizeSecrets(policy, composePresent, kubeSummary.externalEnv)
	passedChecks, failedChecks := countChecks(checks)
	live := liveReadiness()
	passed := failedChecks == 0
	productionReady := passed && live.VaultAddrConfigured && live.TokenPathConfigured
	coverage := "native_secret_rotation_plan_contract"
	if productionReady {
		coverage = "native_secret_rotation_live_identity_ready"
	}
	return Report{
		SchemaVersion:   schemaVersion,
		GeneratedAt:     time.Now().UTC().Format(time.RFC3339),
		Passed:          passed,
		ProductionReady: productionReady,
		CoverageLevel:   coverage,
		PolicyPath:      cfg.PolicyPath,
		ComposePath:     cfg.ComposePath,
		EnvExamplePath:  cfg.EnvExamplePath,
		Provider: ProviderSummary{
			Type:                 policy.Provider.Type,
			KVMount:              policy.Provider.KVMount,
			KubernetesAuthMount:  policy.Provider.KubernetesAuthMount,
			Role:                 policy.Provider.Role,
			ExternalSecretsStore: policy.Provider.ExternalSecretsStore,
		},
		WorkloadIdentity: WorkloadIdentitySummary{
			ServiceAccount:                  policy.WorkloadIdentity.ServiceAccount,
			Namespace:                       policy.WorkloadIdentity.Namespace,
			ProjectedTokenAudience:          policy.WorkloadIdentity.ProjectedTokenAudience,
			ProjectedTokenExpirationSeconds: policy.WorkloadIdentity.ProjectedTokenExpirationSeconds,
			SPIFFEID:                        policy.WorkloadIdentity.SPIFFEID,
			ProjectedTokenManifest:          kubeSummary.projectedToken,
		},
		APIKeyRegistry: registrySummary,
		Secrets:        secrets,
		LiveReadiness:  live,
		Checks:         checks,
		Evidence: []EvidenceRef{
			{Name: "secret_rotation_policy", Path: cfg.PolicyPath, SchemaVersion: policy.SchemaVersion, Status: status(passed), Detail: "Vault/workload-identity rotation contract"},
			{Name: "api_key_registry", Path: policy.APIKeyRegistry.Path, SchemaVersion: registry.SchemaVersion, Status: status(registrySummary.HashOnly), Detail: "hash-only local API-key registry"},
			{Name: "kubernetes_secret_management", Path: "infra/kubernetes/secret-management", Status: status(kubeSummary.secretStore && kubeSummary.projectedToken), Detail: "External Secrets plus projected service-account token manifests"},
		},
		Research: researchRefs(),
		Notes: []string{
			"This is plan-mode evidence; no Vault token or secret value is stored in Git.",
			"production_ready is false until VAULT_ADDR and TRYOPS_WORKLOAD_IDENTITY_TOKEN_PATH are configured in a live environment.",
		},
		Summary: ReportSummary{
			PassedChecks:    passedChecks,
			FailedChecks:    failedChecks,
			TotalChecks:     len(checks),
			ManagedSecrets:  len(policy.ManagedSecrets),
			ComposeSecrets:  countComposeSecrets(secrets),
			ExternalSecrets: countExternalSecrets(secrets),
			RotationMaxDays: rotationMax(policy),
		},
	}, nil
}

func summarizeSecrets(policy Policy, composePresent map[string]bool, externalEnv map[string]bool) []SecretSummary {
	secrets := make([]SecretSummary, 0, len(policy.ManagedSecrets))
	for _, secret := range policy.ManagedSecrets {
		secrets = append(secrets, SecretSummary{
			Name:           secret.Name,
			Env:            secret.Env,
			ComposeSecret:  secret.ComposeSecret,
			VaultPath:      secret.VaultPath,
			VaultProperty:  secret.VaultProperty,
			RotationDays:   secret.RotationDays,
			Owner:          secret.Owner,
			ComposePresent: secret.ComposeSecret == "" || composePresent[secret.Name],
			ExternalSecret: externalEnv[secret.Env],
		})
	}
	return secrets
}

func liveReadiness() LiveReadiness {
	vault := os.Getenv("VAULT_ADDR") != ""
	token := os.Getenv("TRYOPS_WORKLOAD_IDENTITY_TOKEN_PATH") != ""
	mode := "plan"
	if vault && token {
		mode = "live_identity_configured"
	}
	return LiveReadiness{VaultAddrConfigured: vault, TokenPathConfigured: token, Mode: mode}
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

func countComposeSecrets(secrets []SecretSummary) int {
	count := 0
	for _, secret := range secrets {
		if secret.ComposeSecret != "" && secret.ComposePresent {
			count++
		}
	}
	return count
}

func countExternalSecrets(secrets []SecretSummary) int {
	count := 0
	for _, secret := range secrets {
		if secret.ExternalSecret {
			count++
		}
	}
	return count
}

func status(ok bool) string {
	if ok {
		return "passed"
	}
	return "failed"
}

func check(name string, passed bool, detail string) Check {
	return Check{Name: name, Passed: passed, Detail: detail}
}

func researchRefs() []ResearchRef {
	return []ResearchRef{
		{Name: "HashiCorp Vault Kubernetes auth", URL: "https://developer.hashicorp.com/vault/docs/auth/kubernetes", Use: "Vault auth role bound to Kubernetes service-account identity"},
		{Name: "Kubernetes service accounts", URL: "https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/", Use: "projected short-lived service-account token contract"},
		{Name: "External Secrets Operator Vault provider", URL: "https://external-secrets.io/latest/provider/hashicorp-vault/", Use: "Vault-backed ExternalSecret sync into runtime Kubernetes secrets"},
		{Name: "SPIFFE/SPIRE workload identity", URL: "https://spiffe.io/docs/latest/spiffe-about/overview/", Use: "future cryptographic workload identity and SVID direction"},
	}
}
