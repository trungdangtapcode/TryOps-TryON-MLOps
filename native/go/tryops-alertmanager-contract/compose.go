package main

import "fmt"

func evaluateCompose(root string, path string, checks *[]Check) (ComposeSummary, error) {
	data, err := readYAML(resolve(root, path))
	if err != nil {
		return ComposeSummary{}, err
	}
	services := object(data["services"])
	alertmanager := object(services["alertmanager"])
	prometheus := object(services["prometheus"])
	image := stringField(alertmanager, "image")
	ports := stringsFrom(alertmanager["ports"])
	volumes := stringsFrom(alertmanager["volumes"])
	depends := object(prometheus["depends_on"])
	prometheusDep := ""
	if value, ok := depends["alertmanager"]; ok {
		prometheusDep = "service_started"
		if condition := stringField(object(value), "condition"); condition != "" {
			prometheusDep = condition
		}
	}
	addCheck(checks, "compose.service.alertmanager.exists", len(alertmanager) > 0, "alertmanager")
	addCheck(checks, "compose.service.alertmanager.image", image == "prom/alertmanager:latest", image)
	addCheck(checks, "compose.service.alertmanager.port", containsText(ports, "TRYOPS_ALERTMANAGER_PORT"), fmt.Sprintf("%v", ports))
	addCheck(checks, "compose.service.alertmanager.config_volume", containsText(volumes, "infra/alertmanager/alertmanager.yml"), fmt.Sprintf("%v", volumes))
	addCheck(checks, "compose.service.alertmanager.healthcheck", len(object(alertmanager["healthcheck"])) > 0, "healthcheck configured")
	addCheck(checks, "compose.prometheus.depends_on_alertmanager", prometheusDep == "service_started", prometheusDep)
	return ComposeSummary{
		Path:          path,
		ServiceImage:  image,
		Ports:         ports,
		Volumes:       volumes,
		PrometheusDep: prometheusDep,
	}, nil
}
