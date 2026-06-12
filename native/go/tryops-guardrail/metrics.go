package main

import (
	"fmt"
	"sort"
	"strings"
	"sync"
)

var metrics = newNativeMetrics()

type nativeMetrics struct {
	mu             sync.Mutex
	requests       map[string]int
	findingsByRisk map[string]int
}

func newNativeMetrics() *nativeMetrics {
	return &nativeMetrics{
		requests:       map[string]int{},
		findingsByRisk: map[string]int{},
	}
}

func (m *nativeMetrics) record(status string, findings []finding) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.requests[status]++
	for _, item := range findings {
		key := item.OWASPID + "|" + item.Action
		m.findingsByRisk[key]++
	}
}

func (m *nativeMetrics) render() string {
	m.mu.Lock()
	defer m.mu.Unlock()
	lines := []string{
		"# HELP tryops_native_guardrail_requests_total Total native guardrail service evaluations by status.",
		"# TYPE tryops_native_guardrail_requests_total counter",
	}
	statuses := sortedKeys(m.requests)
	for _, status := range statuses {
		lines = append(lines, fmt.Sprintf("tryops_native_guardrail_requests_total{status=%q} %d", label(status), m.requests[status]))
	}
	lines = append(lines,
		"# HELP tryops_native_guardrail_findings_total Total native guardrail findings by OWASP risk and action.",
		"# TYPE tryops_native_guardrail_findings_total counter",
	)
	keys := sortedKeys(m.findingsByRisk)
	for _, key := range keys {
		parts := strings.SplitN(key, "|", 2)
		owaspID := parts[0]
		action := ""
		if len(parts) > 1 {
			action = parts[1]
		}
		lines = append(lines, fmt.Sprintf(
			"tryops_native_guardrail_findings_total{owasp_id=%q,action=%q} %d",
			label(owaspID),
			label(action),
			m.findingsByRisk[key],
		))
	}
	return strings.Join(lines, "\n") + "\n"
}

func sortedKeys(values map[string]int) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func label(value string) string {
	return strings.ReplaceAll(strings.ReplaceAll(value, `\`, `\\`), `"`, `\"`)
}
