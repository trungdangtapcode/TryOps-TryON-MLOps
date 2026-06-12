package main

func summarizeResponse(data map[string]interface{}) map[string]interface{} {
	if data == nil {
		return nil
	}
	summary := map[string]interface{}{}
	copyString(summary, data, "schema_version")
	copyString(summary, data, "api_version")
	copyString(summary, data, "status")
	copyString(summary, data, "request_id")
	copyString(summary, data, "job_id")
	copyString(summary, data, "workload")
	copyString(summary, data, "model_alias")
	copyNumber(summary, data, "queue_depth")

	if trace := objectField(data, "trace"); trace != nil {
		traceSummary := map[string]interface{}{}
		copyString(traceSummary, trace, "trace_id")
		copyString(traceSummary, trace, "span_id")
		copyString(traceSummary, trace, "traceparent")
		if len(traceSummary) > 0 {
			summary["trace"] = traceSummary
		}
	}
	if quota := objectField(data, "quota"); quota != nil {
		quotaSummary := map[string]interface{}{}
		copyBool(quotaSummary, quota, "allowed")
		copyString(quotaSummary, quota, "plan")
		copyString(quotaSummary, quota, "reason")
		copyString(quotaSummary, quota, "workload")
		if len(quotaSummary) > 0 {
			summary["quota"] = quotaSummary
		}
	}
	if metrics := objectField(data, "metrics"); metrics != nil {
		metricsSummary := map[string]interface{}{}
		copyNumber(metricsSummary, metrics, "latency_ms")
		copyNumber(metricsSummary, metrics, "tokens_per_second")
		copyNumber(metricsSummary, metrics, "memory_gb")
		if len(metricsSummary) > 0 {
			summary["metrics"] = metricsSummary
		}
	}
	if output := objectField(data, "output"); output != nil {
		outputSummary := map[string]interface{}{}
		copyString(outputSummary, output, "path")
		copyString(outputSummary, output, "checksum")
		copyString(outputSummary, output, "format")
		copyNumber(outputSummary, output, "estimated_tokens")
		copyBool(outputSummary, output, "truncated")
		if len(outputSummary) > 0 {
			summary["output"] = outputSummary
		}
	}
	if result := objectField(data, "result"); result != nil {
		resultSummary := summarizeResponse(result)
		if report := objectField(result, "report"); report != nil {
			if reportOutput := objectField(report, "output"); reportOutput != nil {
				outputSummary := map[string]interface{}{}
				copyString(outputSummary, reportOutput, "path")
				copyString(outputSummary, reportOutput, "checksum")
				copyString(outputSummary, reportOutput, "format")
				resultSummary["output"] = outputSummary
			}
		}
		if len(resultSummary) > 0 {
			summary["result"] = resultSummary
		}
	}
	return summary
}

func copyString(dst map[string]interface{}, src map[string]interface{}, key string) {
	if value := stringField(src, key); value != "" {
		dst[key] = value
	}
}

func copyNumber(dst map[string]interface{}, src map[string]interface{}, key string) {
	value, ok := src[key]
	if !ok || value == nil {
		return
	}
	switch typed := value.(type) {
	case float64:
		dst[key] = typed
	case int:
		dst[key] = typed
	}
}

func copyBool(dst map[string]interface{}, src map[string]interface{}, key string) {
	value, ok := src[key]
	if !ok || value == nil {
		return
	}
	typed, ok := value.(bool)
	if ok {
		dst[key] = typed
	}
}
