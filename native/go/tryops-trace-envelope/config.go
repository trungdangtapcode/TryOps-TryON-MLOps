package main

import "flag"

type Config struct {
	InputPath  string
	OutputPath string
	Root       string
}

func parseConfig() Config {
	cfg := Config{}
	flag.StringVar(&cfg.InputPath, "input", "", "JSON file containing an envelope array or {\"envelopes\": [...]}.")
	flag.StringVar(&cfg.OutputPath, "output", "artifacts/eval/trace_envelope/native_trace_envelope_report.json", "report output path")
	flag.StringVar(&cfg.Root, "root", ".", "repository root used for relative output paths")
	flag.Parse()
	return cfg
}
