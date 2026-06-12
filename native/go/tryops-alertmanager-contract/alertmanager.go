package main

import "fmt"

func evaluateAlertmanager(root string, path string, checks *[]Check) (AlertmanagerSummary, error) {
	data, err := readYAML(resolve(root, path))
	if err != nil {
		return AlertmanagerSummary{}, err
	}
	route := object(data["route"])
	defaultReceiver := stringField(route, "receiver")
	groupBy := stringsFrom(route["group_by"])
	routes := objects(route["routes"])
	receivers := objects(data["receivers"])
	inhibitRules := objects(data["inhibit_rules"])
	receiverNames := make([]string, 0, len(receivers))
	pageWebhookURL := ""
	for _, receiver := range receivers {
		name := stringField(receiver, "name")
		receiverNames = append(receiverNames, name)
		if name != "tryops-page-webhook" {
			continue
		}
		webhooks := objects(receiver["webhook_configs"])
		if len(webhooks) > 0 {
			pageWebhookURL = stringField(webhooks[0], "url")
		}
	}
	matchers := []string{}
	for _, route := range routes {
		matchers = append(matchers, stringsFrom(route["matchers"])...)
	}

	addCheck(checks, "alertmanager.route.default_receiver", defaultReceiver == "tryops-ticket-log", defaultReceiver)
	addCheck(checks, "alertmanager.route.group_by.alertname", containsValue(groupBy, "alertname"), fmt.Sprintf("%v", groupBy))
	addCheck(checks, "alertmanager.route.group_by.workload", containsValue(groupBy, "workload"), fmt.Sprintf("%v", groupBy))
	addCheck(checks, "alertmanager.route.group_by.severity", containsValue(groupBy, "severity"), fmt.Sprintf("%v", groupBy))
	addCheck(checks, "alertmanager.route.page_matcher", containsValue(matchers, `severity="page"`), fmt.Sprintf("%v", matchers))
	addCheck(checks, "alertmanager.route.ticket_matcher", containsValue(matchers, `severity=~"warning|ticket"`), fmt.Sprintf("%v", matchers))
	addCheck(checks, "alertmanager.receiver.ticket", containsValue(receiverNames, "tryops-ticket-log"), fmt.Sprintf("%v", receiverNames))
	addCheck(checks, "alertmanager.receiver.page_webhook", pageWebhookURL == "http://controller:18082/alerts/webhook", pageWebhookURL)
	addCheck(checks, "alertmanager.inhibit_rules", len(inhibitRules) > 0, fmt.Sprintf("%d", len(inhibitRules)))

	return AlertmanagerSummary{
		Path:            path,
		DefaultReceiver: defaultReceiver,
		GroupBy:         groupBy,
		Receivers:       receiverNames,
		PageWebhookURL:  pageWebhookURL,
		Matchers:        matchers,
		InhibitRules:    len(inhibitRules),
	}, nil
}
