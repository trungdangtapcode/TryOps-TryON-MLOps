package main

import "fmt"

func evaluateCollector(root string, path string, checks *[]Check) (CollectorSummary, error) {
	fullPath := resolve(root, path)
	data, err := readYAML(fullPath)
	if err != nil {
		return CollectorSummary{}, err
	}
	receivers := nestedObject(data, "receivers")
	processors := nestedObject(data, "processors")
	exporters := nestedObject(data, "exporters")
	extensions := nestedObject(data, "extensions")
	pipelines := nestedObject(data, "service", "pipelines")

	otlpGRPC := stringField(nestedObject(receivers, "otlp", "protocols", "grpc"), "endpoint")
	otlpHTTP := stringField(nestedObject(receivers, "otlp", "protocols", "http"), "endpoint")
	filelog := nestedObject(receivers, "filelog/tryops")
	filelogIncludes := stringList(filelog["include"])
	healthEndpoint := stringField(nestedObject(extensions, "health_check"), "endpoint")

	addCheck(checks, "collector.receiver.otlp.grpc", otlpGRPC == "0.0.0.0:4317", otlpGRPC)
	addCheck(checks, "collector.receiver.otlp.http", otlpHTTP == "0.0.0.0:4318", otlpHTTP)
	addCheck(checks, "collector.receiver.filelog.tryops", containsText(filelogIncludes, "/var/log/tryops/*.jsonl"), fmt.Sprintf("%v", filelogIncludes))
	addCheck(checks, "collector.processor.memory_limiter", hasKey(processors, "memory_limiter"), "memory limiter processor")
	addCheck(checks, "collector.processor.resource", hasKey(processors, "resource/tryops"), "resource processor")
	addCheck(checks, "collector.processor.batch", hasKey(processors, "batch"), "batch processor")
	addCheck(checks, "collector.exporter.file.traces", hasKey(exporters, "file/traces"), "trace file exporter")
	addCheck(checks, "collector.exporter.file.logs", hasKey(exporters, "file/logs"), "log file exporter")
	addCheck(checks, "collector.exporter.file.metrics", hasKey(exporters, "file/metrics"), "metric file exporter")
	addCheck(checks, "collector.extension.health_check", healthEndpoint == "0.0.0.0:13133", healthEndpoint)
	addPipelineChecks(checks, pipelines)

	return CollectorSummary{
		Path:             path,
		Receivers:        mapKeys(receivers),
		Processors:       mapKeys(processors),
		Exporters:        mapKeys(exporters),
		Pipelines:        mapKeys(pipelines),
		OTLPGRPCEndpoint: otlpGRPC,
		OTLPHTTPEndpoint: otlpHTTP,
		FileLogIncludes:  filelogIncludes,
		HealthEndpoint:   healthEndpoint,
	}, nil
}

func addPipelineChecks(checks *[]Check, pipelines map[string]interface{}) {
	for _, name := range []string{"traces", "logs", "metrics"} {
		pipeline := object(pipelines[name])
		receivers := stringList(pipeline["receivers"])
		processors := stringList(pipeline["processors"])
		exporters := stringList(pipeline["exporters"])
		addCheck(checks, "collector.pipeline."+name+".exists", len(pipeline) > 0, name)
		addCheck(checks, "collector.pipeline."+name+".uses_batch", hasString(processors, "batch"), fmt.Sprintf("%v", processors))
		addCheck(checks, "collector.pipeline."+name+".uses_resource", hasString(processors, "resource/tryops"), fmt.Sprintf("%v", processors))
		addCheck(checks, "collector.pipeline."+name+".has_exporter", len(exporters) > 0, fmt.Sprintf("%v", exporters))
		if name == "logs" {
			addCheck(checks, "collector.pipeline.logs.filelog", hasString(receivers, "filelog/tryops"), fmt.Sprintf("%v", receivers))
		} else {
			addCheck(checks, "collector.pipeline."+name+".otlp", hasString(receivers, "otlp"), fmt.Sprintf("%v", receivers))
		}
	}
}

func hasKey(values map[string]interface{}, key string) bool {
	_, ok := values[key]
	return ok
}
