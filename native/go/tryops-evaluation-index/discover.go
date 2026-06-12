package main

import (
	"os"
	"path/filepath"
	"sort"
	"strings"
)

func discoverJSONReports(root string) ([]string, error) {
	searchRoots := []string{
		filepath.Join(root, "artifacts", "eval"),
		filepath.Join(root, "reports", "generated"),
	}
	var paths []string
	for _, searchRoot := range searchRoots {
		if _, err := os.Stat(searchRoot); err != nil {
			continue
		}
		err := filepath.WalkDir(searchRoot, func(path string, entry os.DirEntry, err error) error {
			if err != nil {
				return err
			}
			if entry.IsDir() {
				return nil
			}
			if strings.EqualFold(filepath.Ext(path), ".json") {
				if strings.Contains(filepath.ToSlash(path), "/artifacts/eval/evaluation_index/") {
					return nil
				}
				paths = append(paths, path)
			}
			return nil
		})
		if err != nil {
			return nil, err
		}
	}
	sort.Strings(paths)
	return paths, nil
}

func relPath(root string, path string) string {
	rel, err := filepath.Rel(root, path)
	if err != nil {
		return path
	}
	return filepath.ToSlash(rel)
}
