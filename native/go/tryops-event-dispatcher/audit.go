package main

import (
	"encoding/json"
	"os"
	"path/filepath"
)

func writeAuditLog(path string, events []Event) (map[string]bool, error) {
	written := map[string]bool{}
	if path == "" {
		return written, nil
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return written, err
	}
	file, err := os.Create(path)
	if err != nil {
		return written, err
	}
	defer file.Close()
	encoder := json.NewEncoder(file)
	for _, event := range events {
		record := auditRecord{
			SchemaVersion: "tryops.native_audit_event.v1",
			EventID:       event.ID,
			Type:          event.Type,
			Subject:       event.Subject,
			Source:        event.Source,
			Time:          event.Time,
			TenantID:      event.TenantID,
			Actor:         event.Actor,
			Data:          event.Data,
		}
		if err := encoder.Encode(record); err != nil {
			return written, err
		}
		written[event.ID] = true
	}
	return written, nil
}
