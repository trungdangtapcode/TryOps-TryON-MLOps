package main

import (
	"context"
	"net/http"
)

func dispatchEvents(ctx context.Context, client *http.Client, cfg config, events []Event) ([]eventResult, error) {
	if err := validateEvents(events); err != nil {
		return nil, err
	}
	auditWritten, auditErr := writeAuditLog(cfg.AuditLogPath, events)
	webhookResults := dispatchWebhooks(ctx, client, cfg, events)
	results := make([]eventResult, 0, len(events))
	for _, event := range events {
		result := webhookResults[event.ID]
		result.EventID = event.ID
		result.Type = event.Type
		result.Subject = event.Subject
		result.AuditWritten = auditWritten[event.ID]
		if auditErr != nil {
			result.Errors = append(result.Errors, auditErr.Error())
		}
		results = append(results, result)
	}
	return results, auditErr
}
