package main

import (
	"fmt"
	"strings"
)

type manifestSummary struct {
	externalEnv    map[string]bool
	projectedToken bool
	secretStore    bool
	serviceAccount bool
}

func validateKubernetes(root string, policy Policy) ([]Check, manifestSummary) {
	summary := manifestSummary{externalEnv: map[string]bool{}}
	checks := []Check{}
	for _, path := range policy.RequiredManifests {
		docs, err := readYAMLDocuments(root, path)
		if err != nil {
			checks = append(checks, Check{Name: "manifest." + path, Passed: false, Detail: err.Error()})
			continue
		}
		for _, doc := range docs {
			switch doc.Kind {
			case "ServiceAccount":
				name := metadataString(doc.Metadata, "name")
				namespace := metadataString(doc.Metadata, "namespace")
				automountDisabled := doc.AutomountServiceAccountToken != nil && !*doc.AutomountServiceAccountToken
				if name == policy.WorkloadIdentity.ServiceAccount && namespace == policy.WorkloadIdentity.Namespace && automountDisabled {
					summary.serviceAccount = true
				}
			case "SecretStore":
				if secretStoreMatches(doc, policy) {
					summary.secretStore = true
				}
			case "ExternalSecret":
				for _, env := range externalSecretKeys(doc) {
					summary.externalEnv[env] = true
				}
			case "Deployment":
				if deploymentHasProjectedToken(doc, policy) {
					summary.projectedToken = true
				}
			}
		}
		checks = append(checks, check("manifest."+path+".parsed", len(docs) > 0, fmt.Sprintf("%d docs", len(docs))))
	}
	checks = append(checks, check("kubernetes.service_account.no_automount", summary.serviceAccount, policy.WorkloadIdentity.ServiceAccount))
	checks = append(checks, check("kubernetes.secretstore.vault_kubernetes_auth", summary.secretStore, policy.Provider.ExternalSecretsStore))
	checks = append(checks, check("kubernetes.deployment.projected_service_account_token", summary.projectedToken, policy.WorkloadIdentity.ProjectedTokenAudience))
	for _, secret := range policy.ManagedSecrets {
		checks = append(checks, check("external_secret."+secret.Env, summary.externalEnv[secret.Env], secret.VaultPath+"/"+secret.VaultProperty))
	}
	return checks, summary
}

func secretStoreMatches(doc KubernetesDoc, policy Policy) bool {
	name := metadataString(doc.Metadata, "name")
	namespace := metadataString(doc.Metadata, "namespace")
	if name != policy.Provider.ExternalSecretsStore || namespace != policy.WorkloadIdentity.Namespace {
		return false
	}
	text := fmt.Sprintf("%v", doc.Spec)
	return strings.Contains(text, policy.Provider.KVMount) &&
		strings.Contains(text, policy.Provider.KubernetesAuthMount) &&
		strings.Contains(text, policy.Provider.Role) &&
		strings.Contains(text, policy.WorkloadIdentity.ServiceAccount)
}

func externalSecretKeys(doc KubernetesDoc) []string {
	out := []string{}
	data, ok := doc.Spec["data"].([]interface{})
	if !ok {
		return out
	}
	for _, item := range data {
		entry, ok := item.(map[string]interface{})
		if !ok {
			continue
		}
		if key, ok := entry["secretKey"].(string); ok {
			out = append(out, key)
		}
	}
	return out
}

func deploymentHasProjectedToken(doc KubernetesDoc, policy Policy) bool {
	template := nestedMap(doc.Spec, "template")
	spec := nestedMap(template, "spec")
	if stringValue(spec["serviceAccountName"]) != policy.WorkloadIdentity.ServiceAccount {
		return false
	}
	if auto, ok := spec["automountServiceAccountToken"].(bool); !ok || auto {
		return false
	}
	return strings.Contains(fmt.Sprintf("%v", spec), "serviceAccountToken") &&
		strings.Contains(fmt.Sprintf("%v", spec), policy.WorkloadIdentity.ProjectedTokenAudience) &&
		strings.Contains(fmt.Sprintf("%v", spec), fmt.Sprintf("%d", policy.WorkloadIdentity.ProjectedTokenExpirationSeconds))
}

func metadataString(meta map[string]interface{}, key string) string {
	if value, ok := meta[key].(string); ok {
		return value
	}
	return ""
}

func nestedMap(root map[string]interface{}, key string) map[string]interface{} {
	value, ok := root[key].(map[string]interface{})
	if !ok {
		return map[string]interface{}{}
	}
	return value
}

func stringValue(value interface{}) string {
	if text, ok := value.(string); ok {
		return text
	}
	return ""
}
