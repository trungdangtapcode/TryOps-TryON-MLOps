package main

import (
	"os"
	"path/filepath"
	"strings"
)

func sourceContains(root string, relPaths []string, needle string) (bool, error) {
	for _, relPath := range relPaths {
		path := filepath.Join(root, relPath)
		info, err := os.Stat(path)
		if err != nil {
			return false, err
		}
		if info.IsDir() {
			found, err := directoryContains(path, needle)
			if err != nil || found {
				return found, err
			}
			continue
		}
		body, err := os.ReadFile(path)
		if err != nil {
			return false, err
		}
		if strings.Contains(string(body), needle) {
			return true, nil
		}
	}
	return false, nil
}

func directoryContains(path string, needle string) (bool, error) {
	found := false
	err := filepath.WalkDir(path, func(candidate string, entry os.DirEntry, err error) error {
		if err != nil || found || entry.IsDir() {
			return err
		}
		body, err := os.ReadFile(candidate)
		if err != nil {
			return err
		}
		if strings.Contains(string(body), needle) {
			found = true
		}
		return nil
	})
	return found, err
}
