package main

import (
	"fmt"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

func evaluateContracts(cfg Config, compose composeFile) contractReport {
	checks := make([]contractCheck, 0)
	services := make([]serviceSummary, 0)
	secrets := make([]secretSummary, 0)
	for _, contract := range expectedServices() {
		services = append(services, serviceSummary{
			Name:            contract.Name,
			RequiredEnv:     contract.RequiredEnv,
			RequiredPorts:   contract.RequiredPorts,
			RequireHealth:   contract.RequireHealth,
			RequiredDepends: contract.RequiredDepends,
			RequiredSecrets: contract.RequiredSecrets,
		})

		service, exists := compose.Services[contract.Name]
		checks = append(checks, contractCheck{
			Name:   fmt.Sprintf("service.%s.exists", contract.Name),
			Passed: exists,
			Detail: detailFor(exists, "service is present", "service is missing"),
		})
		if !exists {
			continue
		}
		checks = append(checks, environmentChecks(contract.Name, service, contract.RequiredEnv)...)
		checks = append(checks, portChecks(contract.Name, service, contract.RequiredPorts)...)
		checks = append(checks, serviceSecretChecks(contract.Name, service, contract.RequiredSecrets)...)
		if contract.RequireHealth {
			checks = append(checks, contractCheck{
				Name:   fmt.Sprintf("service.%s.healthcheck", contract.Name),
				Passed: len(service.Healthcheck) > 0,
				Detail: detailFor(len(service.Healthcheck) > 0, "healthcheck configured", "healthcheck missing"),
			})
		}
		checks = append(checks, dependencyChecks(contract.Name, service, contract.RequiredDepends)...)
	}
	for _, contract := range expectedSecrets() {
		secrets = append(secrets, secretSummary{Name: contract.Name, Environment: contract.Environment})
	}
	checks = append(checks, secretDefinitionChecks(compose, expectedSecrets())...)
	checks = append(checks, directCredentialChecks(compose)...)
	checks = append(checks, envExampleChecks(cfg.Root, requiredEnvExampleVars())...)
	checks = append(checks, volumeChecks(compose, requiredVolumes())...)
	checks = append(checks, gatewayEnvSourceChecks(cfg.Root)...)

	passed := true
	for _, check := range checks {
		if !check.Passed {
			passed = false
			break
		}
	}
	sort.Slice(services, func(left int, right int) bool {
		return services[left].Name < services[right].Name
	})
	return contractReport{
		SchemaVersion: "tryops.native_config_contract.v1",
		GeneratedAt:   time.Now().UTC().Format(time.RFC3339),
		Passed:        passed,
		CoverageLevel: coverageLevel(passed),
		ComposePath:   filepath.ToSlash(cfg.ComposePath),
		Services:      services,
		Secrets:       secrets,
		Checks:        checks,
		Notes: []string{
			"Native contract check parses docker-compose.yml and fails on missing service envs, secrets, healthchecks, readiness conditions, port variables, or volumes.",
			"Gateway environment variables are also checked against Rust source to catch compose/source drift.",
			".env.example is checked for every required secret variable while .env remains untracked.",
		},
	}
}

func environmentChecks(serviceName string, service composeService, required []string) []contractCheck {
	checks := make([]contractCheck, 0, len(required))
	for _, name := range required {
		_, exists := service.Environment[name]
		checks = append(checks, contractCheck{
			Name:   fmt.Sprintf("service.%s.env.%s", serviceName, name),
			Passed: exists,
			Detail: detailFor(exists, "environment variable configured", "environment variable missing"),
		})
	}
	return checks
}

func portChecks(serviceName string, service composeService, required []string) []contractCheck {
	checks := make([]contractCheck, 0, len(required))
	for _, variable := range required {
		found := false
		for _, port := range service.Ports {
			if strings.Contains(port, "${"+variable) {
				found = true
				break
			}
		}
		checks = append(checks, contractCheck{
			Name:   fmt.Sprintf("service.%s.port.%s", serviceName, variable),
			Passed: found,
			Detail: detailFor(found, "port interpolation configured", "port interpolation missing"),
		})
	}
	return checks
}

func dependencyChecks(serviceName string, service composeService, required map[string]string) []contractCheck {
	checks := make([]contractCheck, 0, len(required))
	keys := sortedMapKeys(required)
	for _, dependency := range keys {
		expected := required[dependency]
		actual, exists := service.DependsOn[dependency]
		passed := exists && actual == expected
		detail := fmt.Sprintf("expected %s, got %s", expected, actual)
		if !exists {
			detail = "dependency missing"
		}
		checks = append(checks, contractCheck{
			Name:   fmt.Sprintf("service.%s.depends_on.%s", serviceName, dependency),
			Passed: passed,
			Detail: detail,
		})
	}
	return checks
}

func volumeChecks(compose composeFile, required []string) []contractCheck {
	checks := make([]contractCheck, 0, len(required))
	for _, volume := range required {
		_, exists := compose.Volumes[volume]
		checks = append(checks, contractCheck{
			Name:   fmt.Sprintf("volume.%s", volume),
			Passed: exists,
			Detail: detailFor(exists, "volume configured", "volume missing"),
		})
	}
	return checks
}

func gatewayEnvSourceChecks(root string) []contractCheck {
	sourcePaths := []string{
		"native/rust/tryops-gateway/src",
		"Dockerfile.gateway",
	}
	checks := make([]contractCheck, 0, len(gatewaySourceEnvVars()))
	for _, envVar := range gatewaySourceEnvVars() {
		found, err := sourceContains(root, sourcePaths, envVar)
		detail := "gateway env referenced in Rust source or gateway Dockerfile"
		if err != nil {
			detail = err.Error()
		} else if !found {
			detail = "gateway env not referenced by Rust source or gateway Dockerfile"
		}
		checks = append(checks, contractCheck{
			Name:   fmt.Sprintf("gateway_source.env.%s", envVar),
			Passed: err == nil && found,
			Detail: detail,
		})
	}
	return checks
}

func sortedMapKeys(values map[string]string) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func detailFor(passed bool, good string, bad string) string {
	if passed {
		return good
	}
	return bad
}

func coverageLevel(passed bool) string {
	if passed {
		return "native_compose_env_healthcheck_contract"
	}
	return "contract_gaps_detected"
}
