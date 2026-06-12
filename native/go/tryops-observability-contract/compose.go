package main

import "fmt"

func evaluateCompose(root string, path string, checks *[]Check) (ComposeSummary, error) {
	fullPath := resolve(root, path)
	data, err := readYAML(fullPath)
	if err != nil {
		return ComposeSummary{}, err
	}
	services := nestedObject(data, "services")
	otel := object(services["otel-collector"])
	prometheus := object(services["prometheus"])
	image := stringField(otel, "image")
	ports := stringList(otel["ports"])
	volumes := stringList(otel["volumes"])
	depends := object(prometheus["depends_on"])
	prometheusDepends := ""
	if _, ok := depends["otel-collector"]; ok {
		prometheusDepends = "service_started"
		nested := object(depends["otel-collector"])
		if condition := stringField(nested, "condition"); condition != "" {
			prometheusDepends = condition
		}
	}

	addCheck(checks, "compose.service.otel_collector.exists", len(otel) > 0, "otel-collector")
	addCheck(checks, "compose.service.otel_collector.image", contains(image, "otel/opentelemetry-collector-contrib"), image)
	addCheck(checks, "compose.service.otel_collector.grpc_port", containsText(ports, "TRYOPS_OTEL_GRPC_PORT"), fmt.Sprintf("%v", ports))
	addCheck(checks, "compose.service.otel_collector.http_port", containsText(ports, "TRYOPS_OTEL_HTTP_PORT"), fmt.Sprintf("%v", ports))
	addCheck(checks, "compose.service.otel_collector.metrics_port", containsText(ports, "TRYOPS_OTEL_METRICS_PORT"), fmt.Sprintf("%v", ports))
	addCheck(checks, "compose.service.otel_collector.config_volume", containsText(volumes, "infra/otel/collector.yml"), fmt.Sprintf("%v", volumes))
	addCheck(checks, "compose.service.otel_collector.log_volume", containsText(volumes, "artifacts/logs"), fmt.Sprintf("%v", volumes))
	addCheck(checks, "compose.service.otel_collector.healthcheck", len(object(otel["healthcheck"])) > 0, "healthcheck configured")
	addCheck(checks, "compose.prometheus.depends_on_otel", prometheusDepends == "service_started", prometheusDepends)

	return ComposeSummary{
		Path:            path,
		ServiceImage:    image,
		Ports:           ports,
		Volumes:         volumes,
		PrometheusNeeds: prometheusDepends,
	}, nil
}
