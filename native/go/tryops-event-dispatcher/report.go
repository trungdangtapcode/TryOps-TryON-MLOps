package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

func buildReport(mode string, receiver receiverSummary, results []eventResult) dispatchReport {
	passed := true
	auditWritten := 0
	webhookDelivered := 0
	failed := 0
	for _, result := range results {
		if result.AuditWritten {
			auditWritten++
		}
		if result.WebhookSent {
			webhookDelivered++
		}
		if len(result.Errors) > 0 || !result.AuditWritten || (receiver.Enabled && !result.WebhookSent) {
			passed = false
			failed++
		}
	}
	return dispatchReport{
		SchemaVersion: "tryops.native_event_dispatcher.v1",
		GeneratedAt:   time.Now().UTC().Format(time.RFC3339),
		Mode:          mode,
		Passed:        passed,
		Receiver:      receiver,
		Summary: reportSummary{
			Events:           len(results),
			AuditWritten:     auditWritten,
			WebhookDelivered: webhookDelivered,
			Failed:           failed,
		},
		Results: results,
	}
}

func writeReport(path string, report dispatchReport) error {
	if path == "" {
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	payload, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(payload, '\n'), 0o644)
}

func printReport(report dispatchReport) {
	for _, result := range report.Results {
		status := "FAIL"
		if len(result.Errors) == 0 && result.AuditWritten && (!report.Receiver.Enabled || result.WebhookSent) {
			status = "PASS"
		}
		fmt.Printf("%s %s audit=%t webhook=%t attempts=%d\n", status, result.EventID, result.AuditWritten, result.WebhookSent, result.Attempts)
		for _, err := range result.Errors {
			fmt.Printf("  %s\n", err)
		}
	}
}
