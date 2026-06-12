package main

import "fmt"

func loadRollbackSummary(root string, path string) (RollbackSummary, error) {
	var state RollbackState
	if err := readJSON(root, path, &state); err != nil {
		return RollbackSummary{Path: path}, err
	}
	record := state.LatestRollback
	return RollbackSummary{
		Path:                  path,
		SchemaVersion:         state.SchemaVersion,
		RecordSchemaVersion:   record.SchemaVersion,
		Status:                record.Status,
		PackageID:             record.PackageID,
		RestoredCandidateID:   record.RestoredCandidateID,
		RolledBackCandidateID: record.RolledBackCandidateID,
		TriggeredBy:           record.TriggeredBy,
	}, nil
}

func validateRollback(summary RollbackSummary) []string {
	var failures []string
	if summary.SchemaVersion != "tryops.rollback_state.v1" {
		failures = append(failures, "rollback state schema_version must be tryops.rollback_state.v1")
	}
	if summary.RecordSchemaVersion != "tryops.rollback_record.v1" {
		failures = append(failures, "rollback record schema_version must be tryops.rollback_record.v1")
	}
	if summary.Status == "" {
		failures = append(failures, "rollback status is required")
	}
	if summary.RestoredCandidateID == "" {
		failures = append(failures, "restored candidate id is required")
	}
	if summary.RolledBackCandidateID == "" {
		failures = append(failures, "rolled back candidate id is required")
	}
	return failures
}

func rollbackCheck(summary RollbackSummary, err error) Check {
	if err != nil {
		return Check{Name: "rollback_state_loaded", Passed: false, Detail: fmt.Sprintf("failed to load %s: %v", summary.Path, err)}
	}
	failures := validateRollback(summary)
	if len(failures) > 0 {
		return Check{Name: "rollback_state_loaded", Passed: false, Detail: joinFailures(failures)}
	}
	return Check{Name: "rollback_state_loaded", Passed: true, Detail: "rollback state and latest rollback record are present"}
}
