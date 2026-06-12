package main

import (
	"flag"
	"path/filepath"
)

func parseConfig() Config {
	root := flag.String("root", ".", "repository root")
	compose := flag.String("compose", "docker-compose.yml", "compose file path, relative to root unless absolute")
	output := flag.String("output", "artifacts/eval/config/native_config_contract_report.json", "report output path")
	flag.Parse()

	cfg := Config{
		Root:        *root,
		ComposePath: *compose,
		OutputPath:  *output,
	}
	if !filepath.IsAbs(cfg.ComposePath) {
		cfg.ComposePath = filepath.Join(cfg.Root, cfg.ComposePath)
	}
	if cfg.OutputPath != "" && !filepath.IsAbs(cfg.OutputPath) {
		cfg.OutputPath = filepath.Join(cfg.Root, cfg.OutputPath)
	}
	return cfg
}
