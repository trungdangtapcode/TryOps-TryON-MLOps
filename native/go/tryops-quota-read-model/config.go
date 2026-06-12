package main

import "flag"

type Config struct {
	InputPath  string
	OutputPath string
}

func parseConfig() Config {
	cfg := Config{}
	flag.StringVar(&cfg.InputPath, "input", "artifacts/eval/quota/quota_usage.json", "quota usage or native quota batch JSON input")
	flag.StringVar(&cfg.OutputPath, "output", "artifacts/eval/quota/native_quota_read_model.json", "read model output path")
	flag.Parse()
	return cfg
}
