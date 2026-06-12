package main

import (
	"encoding/json"
	"fmt"
	"os"
)

func loadQuotaUsage(path string) (QuotaUsageReport, error) {
	var report QuotaUsageReport
	content, err := os.ReadFile(path)
	if err != nil {
		return report, err
	}
	if err := json.Unmarshal(content, &report); err != nil {
		return report, fmt.Errorf("parse quota input: %w", err)
	}
	if report.Snapshot.SchemaVersion == "" {
		var batch struct {
			SchemaVersion string          `json:"schema_version"`
			Engine        string          `json:"engine"`
			Available     bool            `json:"available"`
			Decisions     []QuotaDecision `json:"decisions"`
			Snapshot      QuotaSnapshot   `json:"snapshot"`
		}
		if err := json.Unmarshal(content, &batch); err != nil {
			return report, fmt.Errorf("parse native batch: %w", err)
		}
		report.SchemaVersion = batch.SchemaVersion
		report.NativeQuota = NativeQuotaInfo{Engine: batch.Engine, Available: batch.Available, Reason: "native_batch_input"}
		report.Decisions = batch.Decisions
		report.Snapshot = batch.Snapshot
	}
	return report, nil
}
