package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

func secretDefinitionChecks(compose composeFile, required []secretContract) []contractCheck {
	checks := make([]contractCheck, 0, len(required)*2)
	for _, contract := range required {
		secret, exists := compose.Secrets[contract.Name]
		checks = append(checks, contractCheck{
			Name:   fmt.Sprintf("secret.%s.exists", contract.Name),
			Passed: exists,
			Detail: detailFor(exists, "secret declared", "secret missing"),
		})
		if !exists {
			continue
		}
		checks = append(checks, contractCheck{
			Name:   fmt.Sprintf("secret.%s.environment", contract.Name),
			Passed: secret.Environment == contract.Environment,
			Detail: fmt.Sprintf("expected %s, got %s", contract.Environment, secret.Environment),
		})
	}
	return checks
}

func serviceSecretChecks(serviceName string, service composeService, required []string) []contractCheck {
	checks := make([]contractCheck, 0, len(required))
	for _, name := range required {
		found := contains(service.Secrets, name)
		checks = append(checks, contractCheck{
			Name:   fmt.Sprintf("service.%s.secret.%s", serviceName, name),
			Passed: found,
			Detail: detailFor(found, "secret mounted", "secret missing from service"),
		})
	}
	return checks
}

func directCredentialChecks(compose composeFile) []contractCheck {
	forbidden := map[string][]string{
		"postgres": {"POSTGRES_PASSWORD"},
		"minio":    {"MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD"},
		"mlflow":   {"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"},
		"gateway":  {"TRYOPS_GATEWAY_QUOTA_POSTGRES_DSN"},
	}
	checks := make([]contractCheck, 0)
	for serviceName, names := range forbidden {
		service := compose.Services[serviceName]
		for _, name := range names {
			_, exists := service.Environment[name]
			checks = append(checks, contractCheck{
				Name:   fmt.Sprintf("service.%s.env.%s.direct_secret_absent", serviceName, name),
				Passed: !exists,
				Detail: detailFor(!exists, "direct credential env absent", "direct credential env present"),
			})
		}
	}
	for _, snippet := range []string{
		"POSTGRES_PASSWORD: tryops",
		"MINIO_ROOT_PASSWORD: tryops123",
		"AWS_SECRET_ACCESS_KEY: tryops123",
		"password=tryops",
	} {
		found := strings.Contains(compose.Raw, snippet)
		checks = append(checks, contractCheck{
			Name:   fmt.Sprintf("compose.raw.forbidden.%s", sanitizeCheckName(snippet)),
			Passed: !found,
			Detail: detailFor(!found, "forbidden credential literal absent", "forbidden credential literal present"),
		})
	}
	return checks
}

func envExampleChecks(root string, required []string) []contractCheck {
	path := filepath.Join(root, ".env.example")
	body, err := os.ReadFile(path)
	checks := []contractCheck{
		{
			Name:   "env_example.exists",
			Passed: err == nil,
			Detail: detailFor(err == nil, ".env.example present", ".env.example missing"),
		},
	}
	if err != nil {
		return checks
	}
	text := string(body)
	for _, name := range required {
		found := containsEnvAssignment(text, name)
		checks = append(checks, contractCheck{
			Name:   fmt.Sprintf("env_example.var.%s", name),
			Passed: found,
			Detail: detailFor(found, "documented in .env.example", "missing from .env.example"),
		})
	}
	gitignore, err := os.ReadFile(filepath.Join(root, ".gitignore"))
	ignored := err == nil && containsEnvAssignment(string(gitignore), ".env")
	checks = append(checks, contractCheck{
		Name:   "gitignore.env",
		Passed: ignored,
		Detail: detailFor(ignored, ".env ignored", ".env is not ignored"),
	})
	return checks
}

func contains(values []string, target string) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}

func containsEnvAssignment(text string, name string) bool {
	for _, line := range strings.Split(text, "\n") {
		trimmed := strings.TrimSpace(line)
		if trimmed == name || strings.HasPrefix(trimmed, name+"=") {
			return true
		}
	}
	return false
}

func sanitizeCheckName(value string) string {
	replacer := strings.NewReplacer(" ", "_", ":", "", "=", "_", "/", "_", ".", "_")
	return replacer.Replace(strings.ToLower(value))
}
