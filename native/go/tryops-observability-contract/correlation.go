package main

import (
	"encoding/json"
	"fmt"
)

func evaluateCorrelation(cfg Config, checks *[]Check) (CorrelationSummary, error) {
	traceSample, err := readJSON(resolve(cfg.Root, cfg.TraceSamplePath))
	if err != nil {
		return CorrelationSummary{}, err
	}
	apiSpans, err := readJSONL(resolve(cfg.Root, cfg.APISpanPath))
	if err != nil {
		return CorrelationSummary{}, err
	}
	apiLogs, err := readJSONL(resolve(cfg.Root, cfg.APILogPath))
	if err != nil {
		return CorrelationSummary{}, err
	}
	gatewayLogs, err := readJSONL(resolve(cfg.Root, cfg.GatewayLogPath))
	if err != nil {
		return CorrelationSummary{}, err
	}

	traceIDs := intersectTraceIDs(
		traceIDsFromRecords(gatewayLogs),
		traceIDsFromRecords(apiSpans),
		traceIDsFromRecords(apiLogs),
	)
	serviceNames := serviceNamesFromLogs(apiLogs, gatewayLogs)
	modelCall := modelCallObserved(apiLogs, traceSample)
	redacted := rawPayloadRedacted(apiLogs, gatewayLogs, traceSample)

	addCheck(checks, "correlation.gateway_logs.present", len(gatewayLogs) > 0, fmt.Sprintf("%d logs", len(gatewayLogs)))
	addCheck(checks, "correlation.api_spans.present", len(apiSpans) > 0, fmt.Sprintf("%d spans", len(apiSpans)))
	addCheck(checks, "correlation.api_logs.present", len(apiLogs) > 0, fmt.Sprintf("%d logs", len(apiLogs)))
	addCheck(checks, "correlation.shared_trace_id", len(traceIDs) > 0, fmt.Sprintf("%v", traceIDs))
	addCheck(checks, "correlation.services.gateway_and_api", hasString(serviceNames, "tryops-gateway") && hasString(serviceNames, "tryops-api"), fmt.Sprintf("%v", serviceNames))
	addCheck(checks, "correlation.model_call_observed", modelCall, "LLM model metadata observed in API log or trace sample")
	addCheck(checks, "correlation.raw_payload_redacted", redacted, "raw prompts and private file paths are absent")
	addCheck(checks, "correlation.native_envelope.api", apiLogHasNativeEnvelope(apiLogs), "API native envelope present")
	addCheck(checks, "correlation.native_envelope.gateway", gatewayLogHasNativeEnvelope(gatewayLogs), "gateway native envelope present")

	return CorrelationSummary{
		TraceSamplePath:    cfg.TraceSamplePath,
		APISpanPath:        cfg.APISpanPath,
		APILogPath:         cfg.APILogPath,
		GatewayLogPath:     cfg.GatewayLogPath,
		APISpans:           len(apiSpans),
		APILogs:            len(apiLogs),
		GatewayLogs:        len(gatewayLogs),
		SharedTraceIDs:     traceIDs,
		ServiceNames:       serviceNames,
		ModelCallObserved:  modelCall,
		RawPayloadRedacted: redacted,
	}, nil
}

func traceIDsFromRecords(records []map[string]interface{}) []string {
	values := []string{}
	for _, record := range records {
		if value := stringField(record, "trace_id"); value != "" {
			values = append(values, value)
		}
		trace := object(record["trace"])
		if value := stringField(trace, "trace_id"); value != "" {
			values = append(values, value)
		}
	}
	return uniqueSorted(values)
}

func intersectTraceIDs(groups ...[]string) []string {
	if len(groups) == 0 {
		return nil
	}
	counts := map[string]int{}
	for _, group := range groups {
		for _, value := range uniqueSorted(group) {
			counts[value]++
		}
	}
	out := []string{}
	for value, count := range counts {
		if count == len(groups) {
			out = append(out, value)
		}
	}
	return uniqueSorted(out)
}

func serviceNamesFromLogs(groups ...[]map[string]interface{}) []string {
	values := []string{}
	for _, records := range groups {
		for _, record := range records {
			resource := object(record["resource"])
			if value := stringField(resource, "service.name"); value != "" {
				values = append(values, value)
			}
			envelope := object(record["native_envelope"])
			resource = object(envelope["resource"])
			if value := stringField(resource, "service.name"); value != "" {
				values = append(values, value)
			}
		}
	}
	return uniqueSorted(values)
}

func modelCallObserved(apiLogs []map[string]interface{}, traceSample map[string]interface{}) bool {
	for _, record := range apiLogs {
		attributes := object(record["attributes"])
		if stringField(attributes, "workload") == "llm" && stringField(attributes, "model_alias") != "" {
			return true
		}
	}
	events, _ := traceSample["events"].([]interface{})
	for _, item := range events {
		event := object(item)
		if stringField(event, "workload") == "llm" && stringField(event, "model_alias") != "" {
			return true
		}
	}
	return false
}

func rawPayloadRedacted(apiLogs []map[string]interface{}, gatewayLogs []map[string]interface{}, traceSample map[string]interface{}) bool {
	payload, _ := json.Marshal(map[string]interface{}{
		"api_logs":     apiLogs,
		"gateway_logs": gatewayLogs,
		"trace_sample": traceSample,
	})
	text := string(payload)
	return !contains(text, "private prompt") &&
		!contains(text, "/private/person.png") &&
		!contains(text, "/private/garment.png") &&
		!contains(text, "secret access token")
}

func apiLogHasNativeEnvelope(apiLogs []map[string]interface{}) bool {
	for _, record := range apiLogs {
		envelope := object(record["native_envelope"])
		if stringField(envelope, "schema_version") == "tryops.native_trace_log_envelope.v1" {
			return true
		}
	}
	return false
}

func gatewayLogHasNativeEnvelope(gatewayLogs []map[string]interface{}) bool {
	for _, record := range gatewayLogs {
		if stringField(record, "schema_version") == "tryops.native_trace_log_envelope.v1" {
			return true
		}
	}
	return false
}
