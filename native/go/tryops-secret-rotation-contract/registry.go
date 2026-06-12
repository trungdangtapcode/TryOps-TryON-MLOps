package main

import (
	"fmt"
	"strings"
)

func validateAPIKeyRegistry(policy Policy, registry APIKeyRegistry) ([]Check, APIKeyRegistrySummary) {
	active := 0
	hashOnly := true
	forbidden := []string{}
	requiredRoles := map[string]bool{"viewer": false, "operator": false, "admin": false}
	for _, entry := range registry.Keys {
		if entry.Active {
			active++
			if _, ok := requiredRoles[entry.Role]; ok {
				requiredRoles[entry.Role] = true
			}
		}
		if len(entry.KeyHashSHA256) != 64 || !isLowerHex(entry.KeyHashSHA256) {
			hashOnly = false
			forbidden = append(forbidden, entry.KeyID)
		}
	}
	missingRoles := []string{}
	for role, present := range requiredRoles {
		if !present {
			missingRoles = append(missingRoles, role)
		}
	}
	checks := []Check{
		check("api_key_registry.schema", registry.SchemaVersion == "tryops.api_keys.v1", registry.SchemaVersion),
		check("api_key_registry.hash_only", hashOnly, strings.Join(forbidden, ",")),
		check("api_key_registry.active_keys", active >= 3, fmt.Sprintf("%d active keys", active)),
		check("api_key_registry.required_roles", len(missingRoles) == 0, strings.Join(missingRoles, ",")),
		check("api_key_registry.rotation_policy", policy.APIKeyRegistry.Storage == "hash_only" && policy.APIKeyRegistry.RotationDays <= 90 && policy.APIKeyRegistry.OverlapDays > 0, fmt.Sprintf("rotation=%d overlap=%d", policy.APIKeyRegistry.RotationDays, policy.APIKeyRegistry.OverlapDays)),
	}
	return checks, APIKeyRegistrySummary{
		Path:                  policy.APIKeyRegistry.Path,
		Storage:               policy.APIKeyRegistry.Storage,
		RotationDays:          policy.APIKeyRegistry.RotationDays,
		OverlapDays:           policy.APIKeyRegistry.OverlapDays,
		ActiveKeys:            active,
		Roles:                 sortedRoles(registry.Keys),
		HashOnly:              hashOnly,
		BreakGlassKeyCountMax: policy.APIKeyRegistry.BreakGlassKeyCountMax,
	}
}

func isLowerHex(value string) bool {
	for _, char := range value {
		if !strings.ContainsRune("0123456789abcdef", char) {
			return false
		}
	}
	return true
}
