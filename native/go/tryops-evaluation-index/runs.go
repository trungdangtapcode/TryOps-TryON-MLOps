package main

import (
	"os"
	"path/filepath"
	"sort"
	"strings"
)

func buildPipelineRuns(root string) []pipelineRun {
	generatedRoot := filepath.Join(root, "reports", "generated")
	entries, err := os.ReadDir(generatedRoot)
	if err != nil {
		return nil
	}
	runs := make([]pipelineRun, 0, len(entries))
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		dir := filepath.Join(generatedRoot, entry.Name())
		runContext, err := readJSON(filepath.Join(dir, "run_context.json"))
		if err != nil {
			continue
		}
		openlineage, _ := readJSON(filepath.Join(dir, "openlineage_run_event.json"))
		lineage, _ := readJSON(filepath.Join(dir, "lineage.json"))
		run := pipelineRun{
			RunID:       firstNonEmpty(stringField(runContext, "run_id"), stringField(objectField(openlineage, "run"), "runId")),
			RunName:     stringField(runContext, "run_name"),
			CandidateID: firstNonEmpty(entry.Name(), stringField(lineage, "candidate_id")),
			Workload:    stringField(lineage, "workload"),
			TraceID:     firstNonEmpty(stringField(runContext, "trace_id"), stringField(objectField(objectField(objectField(openlineage, "run"), "facets"), "tryopsRun"), "traceId")),
			CodeVersion: stringField(objectField(runContext, "code"), "version"),
			RiskStatus:  stringField(lineage, "risk_status"),
			Paths: map[string]string{
				"run_context":           relPath(root, filepath.Join(dir, "run_context.json")),
				"openlineage_run_event": relPath(root, filepath.Join(dir, "openlineage_run_event.json")),
				"lineage":               relPath(root, filepath.Join(dir, "lineage.json")),
			},
		}
		fillRunFromOpenLineage(&run, openlineage)
		fillRunFromLineage(&run, lineage)
		runs = append(runs, run)
	}
	sort.Slice(runs, func(i int, j int) bool {
		left := firstNonEmpty(runs[i].EventTime, runs[i].RunID)
		right := firstNonEmpty(runs[j].EventTime, runs[j].RunID)
		return strings.Compare(left, right) > 0
	})
	return runs
}

func fillRunFromOpenLineage(run *pipelineRun, event map[string]interface{}) {
	if event == nil {
		return
	}
	run.EventType = stringField(event, "eventType")
	run.EventTime = stringField(event, "eventTime")
	job := objectField(event, "job")
	run.JobName = stringField(job, "name")
	jobFacet := objectField(objectField(job, "facets"), "tryopsJob")
	run.Workload = firstNonEmpty(run.Workload, stringField(jobFacet, "workload"))
	run.ModelName = firstNonEmpty(run.ModelName, stringField(jobFacet, "modelName"))
	run.ModelVersion = firstNonEmpty(run.ModelVersion, stringField(jobFacet, "modelVersion"))
	run.CodeVersion = firstNonEmpty(run.CodeVersion, stringField(jobFacet, "codeVersion"))
	runFacet := objectField(objectField(objectField(event, "run"), "facets"), "tryopsRun")
	run.CandidateID = firstNonEmpty(run.CandidateID, stringField(runFacet, "candidateId"))
	run.RiskStatus = firstNonEmpty(run.RiskStatus, stringField(runFacet, "riskStatus"))
	run.TraceID = firstNonEmpty(run.TraceID, stringField(runFacet, "traceId"))
	if signed, ok := boolField(runFacet, "signed"); ok {
		run.Signed = signed
	}
	for _, input := range arrayField(event, "inputs") {
		inputObject, ok := input.(map[string]interface{})
		if !ok {
			continue
		}
		datasetFacet := objectField(objectField(inputObject, "facets"), "tryopsDataset")
		if dataset := stringField(datasetFacet, "datasetVersion"); dataset != "" {
			run.DatasetVersion = dataset
			break
		}
	}
}

func fillRunFromLineage(run *pipelineRun, lineage map[string]interface{}) {
	if lineage == nil {
		return
	}
	run.CandidateID = firstNonEmpty(run.CandidateID, stringField(lineage, "candidate_id"))
	run.Workload = firstNonEmpty(run.Workload, stringField(lineage, "workload"))
	run.RiskStatus = firstNonEmpty(run.RiskStatus, stringField(lineage, "risk_status"))
	model := objectField(lineage, "model")
	run.ModelName = firstNonEmpty(run.ModelName, stringField(model, "name"))
	run.ModelVersion = firstNonEmpty(run.ModelVersion, stringField(model, "version"))
	if signed, ok := boolField(model, "signed"); ok {
		run.Signed = signed
	}
	lineageBlock := objectField(lineage, "lineage")
	run.DatasetVersion = firstNonEmpty(run.DatasetVersion, stringField(lineageBlock, "dataset_version"))
	run.CodeVersion = firstNonEmpty(run.CodeVersion, stringField(lineageBlock, "code_version"))
	run.RunID = firstNonEmpty(run.RunID, stringField(lineageBlock, "pipeline_run_id"))
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return value
		}
	}
	return ""
}
