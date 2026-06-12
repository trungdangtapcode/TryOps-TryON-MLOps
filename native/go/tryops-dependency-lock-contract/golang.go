package main

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

func validateGoModules(cfg Config) ([]GoModuleSummary, []Check) {
	checks := []Check{}
	modPaths, err := findGoMods(joinRoot(cfg.RootPath, cfg.GoRootPath))
	checks = append(checks, check("go.modules_discovered", err == nil && len(modPaths) > 0, formatCount(len(modPaths))))
	if err != nil {
		return nil, checks
	}
	summaries := []GoModuleSummary{}
	for _, modPath := range modPaths {
		text, err := os.ReadFile(modPath)
		if err != nil {
			checks = append(checks, check("go."+relPath(cfg.RootPath, modPath)+".read", false, err.Error()))
			continue
		}
		moduleName, requires := parseGoMod(string(text))
		sumPath := filepath.Join(filepath.Dir(modPath), "go.sum")
		sumBody, sumErr := os.ReadFile(sumPath)
		hasSum := sumErr == nil
		coverage := true
		missing := []string{}
		if len(requires) > 0 {
			coverage = hasSum
			for _, req := range requires {
				if !strings.Contains(string(sumBody), req+" ") {
					coverage = false
					missing = append(missing, req)
				}
			}
		}
		rel := relPath(cfg.RootPath, filepath.Dir(modPath))
		checks = append(checks, check("go."+rel+".module_name", moduleName != "", moduleName))
		if len(requires) > 0 {
			checks = append(checks, check("go."+rel+".go_sum_present", hasSum, filepath.ToSlash(sumPath)))
			checks = append(checks, check("go."+rel+".checksum_coverage", coverage, fmt.Sprintf("requires=%d missing=%v", len(requires), missing)))
		}
		summaries = append(summaries, GoModuleSummary{
			Path:             rel,
			Module:           moduleName,
			Requires:         requires,
			HasGoSum:         hasSum,
			ChecksumCoverage: coverage,
		})
	}
	return summaries, checks
}

func findGoMods(root string) ([]string, error) {
	paths := []string{}
	err := filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			name := d.Name()
			if name == ".git" || name == "node_modules" || name == "target" {
				return filepath.SkipDir
			}
			return nil
		}
		if d.Name() == "go.mod" {
			paths = append(paths, path)
		}
		return nil
	})
	sort.Strings(paths)
	return paths, err
}

func parseGoMod(text string) (string, []string) {
	moduleName := ""
	requires := []string{}
	inRequire := false
	for _, raw := range strings.Split(text, "\n") {
		line := strings.TrimSpace(raw)
		if line == "" || strings.HasPrefix(line, "//") {
			continue
		}
		if strings.HasPrefix(line, "module ") {
			moduleName = strings.TrimSpace(strings.TrimPrefix(line, "module "))
			continue
		}
		if line == "require (" {
			inRequire = true
			continue
		}
		if inRequire && line == ")" {
			inRequire = false
			continue
		}
		if strings.HasPrefix(line, "require ") {
			parts := strings.Fields(strings.TrimPrefix(line, "require "))
			if len(parts) >= 2 {
				requires = append(requires, parts[0])
			}
			continue
		}
		if inRequire {
			parts := strings.Fields(line)
			if len(parts) >= 2 {
				requires = append(requires, parts[0])
			}
		}
	}
	sort.Strings(requires)
	return moduleName, requires
}
