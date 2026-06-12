package main

import "flag"

func parseConfig() Config {
	cfg := Config{}
	flag.StringVar(&cfg.RootPath, "root", ".", "repository root")
	flag.StringVar(&cfg.OutputPath, "output", "artifacts/eval/incidents/native_incident_workflow.json", "JSON evidence output path")
	flag.StringVar(&cfg.PostmortemPath, "postmortem-output", "artifacts/eval/incidents/postmortem_bad_candidate.md", "postmortem Markdown output path")
	flag.StringVar(&cfg.TemplatePath, "template", "docs/incident_postmortem_template.md", "postmortem template path")
	flag.StringVar(&cfg.RollbackPath, "rollback", "artifacts/deployments/rollback_state.json", "rollback state artifact path")
	flag.StringVar(&cfg.ControllerPath, "controller", "native/go/tryops-controller", "Go controller source directory")
	flag.StringVar(&cfg.DispatcherPath, "dispatcher", "native/go/tryops-event-dispatcher/events.go", "Go event dispatcher source path")
	flag.Parse()
	return cfg
}
