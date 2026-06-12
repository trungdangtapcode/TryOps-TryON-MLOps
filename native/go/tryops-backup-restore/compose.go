package main

import (
	"os"
	"strings"

	"gopkg.in/yaml.v3"
)

type composeFile struct {
	Services map[string]composeService `yaml:"services"`
	Volumes  map[string]map[string]any `yaml:"volumes"`
	Secrets  map[string]map[string]any `yaml:"secrets"`
}

type composeService struct {
	Image   string   `yaml:"image"`
	Volumes []string `yaml:"volumes"`
	Secrets []string `yaml:"secrets"`
}

func loadCompose(path string) (composeFile, error) {
	var cfg composeFile
	body, err := os.ReadFile(path)
	if err != nil {
		return cfg, err
	}
	if err := yaml.Unmarshal(body, &cfg); err != nil {
		return cfg, err
	}
	if cfg.Services == nil {
		cfg.Services = map[string]composeService{}
	}
	if cfg.Volumes == nil {
		cfg.Volumes = map[string]map[string]any{}
	}
	if cfg.Secrets == nil {
		cfg.Secrets = map[string]map[string]any{}
	}
	return cfg, nil
}

func serviceUsesVolume(service composeService, volume string) bool {
	prefix := volume + ":"
	for _, mount := range service.Volumes {
		if mount == volume || strings.HasPrefix(mount, prefix) {
			return true
		}
	}
	return false
}

func serviceUsesSecret(service composeService, secret string) bool {
	for _, mounted := range service.Secrets {
		if mounted == secret {
			return true
		}
	}
	return false
}
