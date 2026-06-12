package main

import (
	"fmt"
	"os"
	"strings"

	"gopkg.in/yaml.v3"
)

type composeFile struct {
	Services map[string]composeService `yaml:"services"`
	Secrets  map[string]composeSecret  `yaml:"secrets"`
}

type composeService struct {
	Profiles    []string               `yaml:"profiles"`
	Build       map[string]interface{} `yaml:"build"`
	Environment map[string]string      `yaml:"environment"`
	Ports       []string               `yaml:"ports"`
	Secrets     []string               `yaml:"secrets"`
	Healthcheck map[string]interface{} `yaml:"healthcheck"`
}

type composeSecret struct {
	Environment string `yaml:"environment"`
}

func evaluateCompose(path string, checks *[]Check) ComposeSummary {
	summary := ComposeSummary{
		Service:            "gateway-tls",
		Profile:            "tls",
		PortVariable:       "TRYOPS_GATEWAY_TLS_PORT",
		TLSCertSecret:      "tryops_tls_cert",
		TLSKeySecret:       "tryops_tls_key",
		HealthcheckScheme:  "https",
		RequiredEnv:        []string{"TRYOPS_GATEWAY_TLS_CERT_PATH", "TRYOPS_GATEWAY_TLS_KEY_PATH", "TRYOPS_GATEWAY_HEALTH_ADDR"},
		RequiredSecretRefs: []string{"tryops_gateway_quota_postgres_dsn", "tryops_tls_cert", "tryops_tls_key"},
	}
	body, err := os.ReadFile(path)
	if err != nil {
		addCheck(checks, "compose.read", false, err.Error())
		return summary
	}
	addCheck(checks, "compose.read", true, path)
	var compose composeFile
	if err := yaml.Unmarshal(body, &compose); err != nil {
		addCheck(checks, "compose.parse", false, err.Error())
		return summary
	}
	addCheck(checks, "compose.parse", true, "yaml parsed")
	service, ok := compose.Services["gateway-tls"]
	addCheck(checks, "compose.service.gateway_tls", ok, "gateway-tls service")
	if !ok {
		return summary
	}
	addCheck(checks, "compose.gateway_tls.profile", contains(service.Profiles, "tls"), fmt.Sprintf("%v", service.Profiles))
	addCheck(checks, "compose.gateway_tls.dockerfile", fmt.Sprint(service.Build["dockerfile"]) == "Dockerfile.gateway", fmt.Sprint(service.Build["dockerfile"]))
	addCheck(checks, "compose.gateway_tls.port", containsSubstring(service.Ports, "${TRYOPS_GATEWAY_TLS_PORT"), fmt.Sprintf("%v", service.Ports))
	for _, envName := range summary.RequiredEnv {
		addCheck(checks, "compose.gateway_tls.env."+envName, service.Environment[envName] != "", service.Environment[envName])
	}
	addCheck(checks, "compose.gateway_tls.cert_path", service.Environment["TRYOPS_GATEWAY_TLS_CERT_PATH"] == "/run/secrets/tryops_tls_cert", service.Environment["TRYOPS_GATEWAY_TLS_CERT_PATH"])
	addCheck(checks, "compose.gateway_tls.key_path", service.Environment["TRYOPS_GATEWAY_TLS_KEY_PATH"] == "/run/secrets/tryops_tls_key", service.Environment["TRYOPS_GATEWAY_TLS_KEY_PATH"])
	for _, secret := range summary.RequiredSecretRefs {
		addCheck(checks, "compose.gateway_tls.secret."+secret, contains(service.Secrets, secret), strings.Join(service.Secrets, ","))
	}
	health := fmt.Sprint(service.Healthcheck["test"])
	addCheck(checks, "compose.gateway_tls.healthcheck.https", strings.Contains(health, "TRYOPS_GATEWAY_HEALTH_SCHEME=https"), health)
	addCheck(checks, "compose.secret.tryops_tls_cert", compose.Secrets["tryops_tls_cert"].Environment == "TRYOPS_TLS_CERT_PEM", compose.Secrets["tryops_tls_cert"].Environment)
	addCheck(checks, "compose.secret.tryops_tls_key", compose.Secrets["tryops_tls_key"].Environment == "TRYOPS_TLS_KEY_PEM", compose.Secrets["tryops_tls_key"].Environment)
	return summary
}

func contains(values []string, want string) bool {
	for _, value := range values {
		if value == want {
			return true
		}
	}
	return false
}

func containsSubstring(values []string, want string) bool {
	for _, value := range values {
		if strings.Contains(value, want) {
			return true
		}
	}
	return false
}
