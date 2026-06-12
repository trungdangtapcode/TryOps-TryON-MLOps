package main

import (
	"encoding/json"
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
)

func loadManifest(root string, path string) (Manifest, error) {
	var manifest Manifest
	content, err := os.ReadFile(resolve(root, path))
	if err != nil {
		return manifest, err
	}
	if err := json.Unmarshal(content, &manifest); err != nil {
		return manifest, err
	}
	return manifest, nil
}

func loadCompose(root string, path string) (ComposeFile, error) {
	var compose ComposeFile
	content, err := os.ReadFile(resolve(root, path))
	if err != nil {
		return compose, err
	}
	if err := yaml.Unmarshal(content, &compose); err != nil {
		return compose, err
	}
	return compose, nil
}

func resolve(root string, path string) string {
	if filepath.IsAbs(path) {
		return path
	}
	return filepath.Join(root, path)
}
