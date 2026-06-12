package main

import (
	"fmt"
	"sort"
	"strings"
)

func validatePolicy(policy Policy) []Check {
	checks := []Check{
		check("policy.schema", policy.SchemaVersion == "tryops.secret_rotation_policy.v1", policy.SchemaVersion),
		check("policy.provider.vault", policy.Provider.Type == "hashicorp_vault", policy.Provider.Type),
		check("policy.provider.kubernetes_auth", policy.Provider.KubernetesAuthMount != "" && policy.Provider.Role != "", policy.Provider.KubernetesAuthMount+"/"+policy.Provider.Role),
		check("policy.workload_identity.projected_token", policy.WorkloadIdentity.ProjectedTokenAudience != "" && policy.WorkloadIdentity.ProjectedTokenExpirationSeconds > 0 && policy.WorkloadIdentity.ProjectedTokenExpirationSeconds <= 3600, fmt.Sprintf("%s/%d", policy.WorkloadIdentity.ProjectedTokenAudience, policy.WorkloadIdentity.ProjectedTokenExpirationSeconds)),
		check("policy.api_key_registry.hash_only", policy.APIKeyRegistry.Storage == "hash_only", policy.APIKeyRegistry.Storage),
		check("policy.api_key_registry.rotation_window", policy.APIKeyRegistry.RotationDays > 0 && policy.APIKeyRegistry.RotationDays <= 90 && policy.APIKeyRegistry.OverlapDays > 0 && policy.APIKeyRegistry.OverlapDays < policy.APIKeyRegistry.RotationDays, fmt.Sprintf("rotation=%d overlap=%d", policy.APIKeyRegistry.RotationDays, policy.APIKeyRegistry.OverlapDays)),
	}
	seen := map[string]bool{}
	envSeen := map[string]bool{}
	for _, secret := range policy.ManagedSecrets {
		name := "policy.managed_secret." + secret.Name
		passed := secret.Name != "" && secret.Env != "" && secret.VaultPath != "" && secret.VaultProperty != "" && secret.RotationDays > 0 && secret.RotationDays <= 90 && secret.Owner != ""
		if seen[secret.Name] {
			passed = false
		}
		if envSeen[secret.Env] {
			passed = false
		}
		checks = append(checks, check(name, passed, fmt.Sprintf("%s %s rotation=%d owner=%s", secret.Env, secret.VaultPath, secret.RotationDays, secret.Owner)))
		seen[secret.Name] = true
		envSeen[secret.Env] = true
	}
	checks = append(checks, check("policy.managed_secret.count", len(policy.ManagedSecrets) >= 8, fmt.Sprintf("%d managed secrets", len(policy.ManagedSecrets))))
	checks = append(checks, check("policy.required_manifests", len(policy.RequiredManifests) >= 2, strings.Join(policy.RequiredManifests, ",")))
	return checks
}

func envSet(policy Policy) map[string]bool {
	out := map[string]bool{}
	for _, secret := range policy.ManagedSecrets {
		out[secret.Env] = true
	}
	return out
}

func sortedRoles(keys []APIKeyEntry) []string {
	values := map[string]bool{}
	for _, key := range keys {
		if key.Role != "" {
			values[key.Role] = true
		}
	}
	roles := make([]string, 0, len(values))
	for role := range values {
		roles = append(roles, role)
	}
	sort.Strings(roles)
	return roles
}

func rotationMax(policy Policy) int {
	max := policy.APIKeyRegistry.RotationDays
	for _, secret := range policy.ManagedSecrets {
		if secret.RotationDays > max {
			max = secret.RotationDays
		}
	}
	return max
}
