package main

import (
	"fmt"
	"strings"
)

func validateCompose(policy Policy, compose ComposeFile, envExample string) ([]Check, map[string]bool) {
	checks := []Check{}
	composePresent := map[string]bool{}
	for _, secret := range policy.ManagedSecrets {
		envInExample := strings.Contains(envExample, secret.Env+"=")
		checks = append(checks, check("env_example."+secret.Env, envInExample, secret.Env))
		if secret.ComposeSecret == "" {
			continue
		}
		declared := compose.Secrets[secret.ComposeSecret]
		present := declared.Environment == secret.Env
		composePresent[secret.Name] = present
		checks = append(checks, check("compose.secret."+secret.ComposeSecret, present, fmt.Sprintf("expected env %s got %s", secret.Env, declared.Environment)))
	}
	checks = append(checks, check("compose.gateway.quota_secret_mount", serviceUsesSecret(compose.Services["gateway"], "tryops_gateway_quota_postgres_dsn"), "gateway mounts quota DSN secret"))
	checks = append(checks, check("compose.gateway_tls.tls_secret_mounts", serviceUsesSecret(compose.Services["gateway-tls"], "tryops_tls_cert") && serviceUsesSecret(compose.Services["gateway-tls"], "tryops_tls_key"), "gateway-tls mounts cert/key secrets"))
	return checks, composePresent
}

func serviceUsesSecret(service ComposeService, name string) bool {
	for _, secret := range service.Secrets {
		if secret == name {
			return true
		}
	}
	return false
}
