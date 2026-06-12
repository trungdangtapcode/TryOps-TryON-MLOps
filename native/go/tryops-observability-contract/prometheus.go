package main

import "fmt"

func evaluatePrometheus(root string, path string, checks *[]Check) (PrometheusSummary, error) {
	fullPath := resolve(root, path)
	data, err := readYAML(fullPath)
	if err != nil {
		return PrometheusSummary{}, err
	}
	ruleFiles := stringList(data["rule_files"])
	configs := listObjects(data["scrape_configs"])
	jobName := ""
	targets := []string{}
	for _, config := range configs {
		if stringField(config, "job_name") != "tryops-otel-collector" {
			continue
		}
		jobName = "tryops-otel-collector"
		for _, staticConfig := range listObjects(config["static_configs"]) {
			targets = append(targets, stringList(staticConfig["targets"])...)
		}
	}
	addCheck(checks, "prometheus.scrape.otel_collector.exists", jobName == "tryops-otel-collector", jobName)
	addCheck(checks, "prometheus.scrape.otel_collector.target", hasString(targets, "otel-collector:8888"), fmt.Sprintf("%v", targets))
	addCheck(checks, "prometheus.rule_files.present", len(ruleFiles) >= 3, fmt.Sprintf("%v", ruleFiles))
	return PrometheusSummary{
		Path:      path,
		JobName:   jobName,
		Targets:   targets,
		RuleFiles: ruleFiles,
	}, nil
}

func listObjects(value interface{}) []map[string]interface{} {
	values := []map[string]interface{}{}
	items, ok := value.([]interface{})
	if !ok {
		return values
	}
	for _, item := range items {
		values = append(values, object(item))
	}
	return values
}
