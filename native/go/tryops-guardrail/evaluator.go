package main

import (
	"regexp"
	"sort"
	"strings"
)

var (
	emailPattern     = regexp.MustCompile(`(?i)\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b`)
	phonePattern     = regexp.MustCompile(`(?i)(?:\+?1[\s.\-]?)?(?:\([0-9]{3}\)|[0-9]{3})[\s.\-]?[0-9]{3}[\s.\-]?[0-9]{4}\b`)
	ssnPattern       = regexp.MustCompile(`\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b`)
	cardPattern      = regexp.MustCompile(`\b(?:[0-9][ -]?){13,19}\b`)
	apiKeyPattern    = regexp.MustCompile(`(?i)\b(?:sk-[A-Za-z0-9]{8,}|AKIA[A-Z0-9]{8,}|(?:api[_-]?key|password|secret|token)\s*[=:]\s*\S+)`)
	repeatForever    = regexp.MustCompile(`(?i)\b(repeat|loop|continue|generate|write)\b.{0,80}\b(forever|without stopping|infinite|until cancelled)\b`)
	systemPromptLeak = regexp.MustCompile(`(?i)\b(system prompt|developer message|hidden instructions?|internal policy|chain of thought)\b`)
)

func evaluate(request guardrailRequest) guardrailResponse {
	findings := []finding{}
	prompt := strings.ToLower(request.Prompt)
	output := strings.ToLower(request.OutputText)

	if hasPII(request.Prompt) {
		findings = append(findings, finding{
			CheckID:  "pii_ingress",
			OWASPID:  "LLM02:2025",
			Risk:     "sensitive_information_disclosure",
			Stage:    "ingress",
			Action:   "redact",
			Severity: "medium",
			Message:  "PII-like input detected; redact before generation",
		})
	}
	if containsAny(prompt, []string{"ignore previous", "ignore all policy", "bypass policy", "jailbreak", "dan mode", "developer mode", "override instructions"}) {
		findings = append(findings, finding{
			CheckID:  "prompt_injection",
			OWASPID:  "LLM01:2025",
			Risk:     "prompt_injection",
			Stage:    "ingress",
			Action:   "block",
			Severity: "high",
			Message:  "Prompt attempts to override application instructions",
		})
	}
	if systemPromptLeak.MatchString(request.Prompt) && containsAny(prompt, []string{"print", "show", "reveal", "dump", "expose"}) {
		findings = append(findings, finding{
			CheckID:  "system_prompt_leakage",
			OWASPID:  "LLM07:2025",
			Risk:     "system_prompt_leakage",
			Stage:    "ingress",
			Action:   "block",
			Severity: "high",
			Message:  "Prompt requests hidden system or developer instructions",
		})
	}
	if containsAny(prompt, []string{"api keys", "api key", "password", "secret", "hidden credential", "deployment environment", "environment variables"}) &&
		containsAny(prompt, []string{"show", "print", "reveal", "dump", "exfiltrate"}) {
		findings = append(findings, finding{
			CheckID:  "secret_disclosure_request",
			OWASPID:  "LLM02:2025",
			Risk:     "sensitive_information_disclosure",
			Stage:    "ingress",
			Action:   "block",
			Severity: "high",
			Message:  "Prompt requests secrets or deployment credentials",
		})
	}
	if repeatForever.MatchString(request.Prompt) || request.MaxTokens > 1024 && containsAny(prompt, []string{"longest possible", "maximum tokens", "as much as possible"}) {
		findings = append(findings, finding{
			CheckID:  "unbounded_consumption",
			OWASPID:  "LLM10:2025",
			Risk:     "unbounded_consumption",
			Stage:    "ingress",
			Action:   "block",
			Severity: "medium",
			Message:  "Prompt attempts to consume unbounded output or compute",
		})
	}
	if containsAny(prompt, []string{"delete database", "run shell", "execute command", "send email to all", "make a purchase"}) {
		findings = append(findings, finding{
			CheckID:  "excessive_agency",
			OWASPID:  "LLM06:2025",
			Risk:     "excessive_agency",
			Stage:    "ingress",
			Action:   "block",
			Severity: "high",
			Message:  "Prompt requests unsafe autonomous action outside the LLM boundary",
		})
	}

	if request.OutputText != "" {
		if apiKeyPattern.MatchString(request.OutputText) {
			findings = append(findings, finding{
				CheckID:  "credential_output",
				OWASPID:  "LLM02:2025",
				Risk:     "sensitive_information_disclosure",
				Stage:    "egress",
				Action:   "block",
				Severity: "critical",
				Message:  "Generated output contains credential-like material",
			})
		}
		if strings.Contains(output, "begin_system_prompt") || strings.Contains(output, "system_prompt=") || strings.Contains(output, "developer_message=") {
			findings = append(findings, finding{
				CheckID:  "system_prompt_output",
				OWASPID:  "LLM07:2025",
				Risk:     "system_prompt_leakage",
				Stage:    "egress",
				Action:   "block",
				Severity: "critical",
				Message:  "Generated output resembles hidden prompt leakage",
			})
		}
	}

	blocked := false
	riskIDs := map[string]bool{}
	for _, item := range findings {
		riskIDs[item.OWASPID] = true
		if item.Action == "block" {
			blocked = true
		}
	}
	ids := make([]string, 0, len(riskIDs))
	for id := range riskIDs {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	status := "passed"
	if blocked {
		status = "blocked"
	}
	return guardrailResponse{
		SchemaVersion: schemaVersion,
		Engine: engine{
			Name:     "tryops-go-guardrail",
			Language: "go",
			Version:  "0.1.0",
		},
		Status:   status,
		Blocked:  blocked,
		RiskIDs:  ids,
		Findings: findings,
	}
}

func hasPII(text string) bool {
	return emailPattern.MatchString(text) ||
		phonePattern.MatchString(text) ||
		ssnPattern.MatchString(text) ||
		cardPattern.MatchString(text) ||
		apiKeyPattern.MatchString(text)
}

func containsAny(text string, terms []string) bool {
	for _, term := range terms {
		if strings.Contains(text, term) {
			return true
		}
	}
	return false
}
