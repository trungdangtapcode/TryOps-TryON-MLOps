package main

import "flag"

type Config struct {
	Root         string
	ManifestPath string
	ComposePath  string
	OutputPath   string
}

func parseConfig() Config {
	cfg := Config{}
	flag.StringVar(&cfg.Root, "root", ".", "repository root")
	flag.StringVar(&cfg.ManifestPath, "manifest", "configs/container_images.json", "container image manifest path")
	flag.StringVar(&cfg.ComposePath, "compose", "docker-compose.yml", "docker compose file path")
	flag.StringVar(&cfg.OutputPath, "output", "artifacts/eval/containers/native_container_contract_report.json", "report output path")
	flag.Parse()
	return cfg
}
