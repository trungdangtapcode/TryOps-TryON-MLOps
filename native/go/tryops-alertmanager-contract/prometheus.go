package main

import "fmt"

func evaluatePrometheus(root string, path string, checks *[]Check) (PrometheusSummary, error) {
	data, err := readYAML(resolve(root, path))
	if err != nil {
		return PrometheusSummary{}, err
	}
	alerting := object(data["alerting"])
	alertmanagers := objects(alerting["alertmanagers"])
	targets := []string{}
	for _, manager := range alertmanagers {
		for _, staticConfig := range objects(manager["static_configs"]) {
			targets = append(targets, stringsFrom(staticConfig["targets"])...)
		}
	}
	ruleFiles := stringsFrom(data["rule_files"])
	scrapeJobs := []string{}
	for _, scrape := range objects(data["scrape_configs"]) {
		scrapeJobs = append(scrapeJobs, stringField(scrape, "job_name"))
	}
	ruleCount, severities, workloads, err := summarizeRules(root, ruleFiles)
	if err != nil {
		return PrometheusSummary{}, err
	}
	addCheck(checks, "prometheus.alerting.alertmanager_target", containsValue(targets, "alertmanager:9093"), fmt.Sprintf("%v", targets))
	addCheck(checks, "prometheus.rules.enterprise", containsText(ruleFiles, "tryops_alerts.yml"), fmt.Sprintf("%v", ruleFiles))
	addCheck(checks, "prometheus.rules.burn_rate", containsText(ruleFiles, "tryops_burn_rate_alerts.yml"), fmt.Sprintf("%v", ruleFiles))
	addCheck(checks, "prometheus.rules.finops", containsText(ruleFiles, "tryops_finops_alerts.yml"), fmt.Sprintf("%v", ruleFiles))
	addCheck(checks, "prometheus.rules.count", ruleCount >= 10, fmt.Sprintf("%d", ruleCount))
	addCheck(checks, "prometheus.rules.severity_page", containsValue(severities, "page"), fmt.Sprintf("%v", severities))
	addCheck(checks, "prometheus.rules.severity_warning", containsValue(severities, "warning"), fmt.Sprintf("%v", severities))
	addCheck(checks, "prometheus.rules.workload_llm", containsValue(workloads, "llm"), fmt.Sprintf("%v", workloads))
	addCheck(checks, "prometheus.rules.workload_vton", containsValue(workloads, "vton"), fmt.Sprintf("%v", workloads))
	return PrometheusSummary{
		Path:           path,
		AlertTargets:   targets,
		RuleFiles:      ruleFiles,
		ScrapeJobs:     scrapeJobs,
		AlertRuleCount: ruleCount,
		Severities:     severities,
		Workloads:      workloads,
	}, nil
}

func summarizeRules(root string, ruleFiles []string) (int, []string, []string, error) {
	count := 0
	severities := map[string]bool{}
	workloads := map[string]bool{}
	for _, file := range ruleFiles {
		data, err := readYAML(resolvePrometheusRule(root, file))
		if err != nil {
			return 0, nil, nil, err
		}
		for _, group := range objects(data["groups"]) {
			for _, rule := range objects(group["rules"]) {
				if stringField(rule, "alert") == "" {
					continue
				}
				count++
				labels := object(rule["labels"])
				if severity := stringField(labels, "severity"); severity != "" {
					severities[severity] = true
				}
				if workload := stringField(labels, "workload"); workload != "" {
					workloads[workload] = true
				}
			}
		}
	}
	return count, mapKeys(severities), mapKeys(workloads), nil
}

func resolvePrometheusRule(root string, path string) string {
	if len(path) >= len("/etc/prometheus/") && path[:len("/etc/prometheus/")] == "/etc/prometheus/" {
		return resolve(root, "infra/prometheus/"+path[len("/etc/prometheus/"):])
	}
	return resolve(root, path)
}
