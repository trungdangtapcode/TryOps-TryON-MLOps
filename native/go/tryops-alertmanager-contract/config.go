package main

import (
	"flag"
	"path/filepath"
)

func parseConfig() Config {
	var cfg Config
	flag.StringVar(&cfg.Root, "root", ".", "repository root")
	flag.StringVar(&cfg.AlertmanagerPath, "alertmanager", "infra/alertmanager/alertmanager.yml", "Alertmanager config path")
	flag.StringVar(&cfg.PrometheusPath, "prometheus", "infra/prometheus/prometheus.yml", "Prometheus config path")
	flag.StringVar(&cfg.ComposePath, "compose", "docker-compose.yml", "Docker Compose path")
	flag.StringVar(&cfg.OutputPath, "output", "artifacts/eval/alerts/native_alertmanager_contract.json", "report output path")
	flag.Parse()
	abs, err := filepath.Abs(cfg.Root)
	if err == nil {
		cfg.Root = abs
	}
	return cfg
}

func resolve(root string, path string) string {
	if filepath.IsAbs(path) {
		return path
	}
	return filepath.Join(root, path)
}
