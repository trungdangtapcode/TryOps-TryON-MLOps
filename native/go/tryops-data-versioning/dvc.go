package main

import (
	"bufio"
	"fmt"
	"io/fs"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

func loadDVCRemote(root string) (DVCRemote, error) {
	path := filepath.Join(root, ".dvc", "config")
	file, err := os.Open(path)
	if err != nil {
		return DVCRemote{}, fmt.Errorf("open DVC config: %w", err)
	}
	defer file.Close()

	remote := DVCRemote{Name: "minio"}
	section := ""
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		if strings.HasPrefix(line, "[") && strings.HasSuffix(line, "]") {
			section = line
			if strings.Contains(line, "remote \"") {
				remote.Name = strings.TrimSuffix(strings.TrimPrefix(line, "['remote \""), "\"']")
			}
			continue
		}
		key, value, ok := strings.Cut(line, "=")
		if !ok {
			continue
		}
		key = strings.TrimSpace(key)
		value = strings.TrimSpace(value)
		if strings.Contains(section, "remote \"") {
			switch key {
			case "url":
				remote.URL = value
			case "endpointurl":
				remote.Endpoint = value
			}
		}
	}
	if err := scanner.Err(); err != nil {
		return DVCRemote{}, fmt.Errorf("scan DVC config: %w", err)
	}
	if remote.URL == "" {
		return DVCRemote{}, fmt.Errorf("DVC remote url is missing")
	}
	if remote.Endpoint == "" {
		return DVCRemote{}, fmt.Errorf("DVC remote endpointurl is missing")
	}
	parsed, err := url.Parse(remote.URL)
	if err != nil {
		return DVCRemote{}, fmt.Errorf("parse DVC remote url: %w", err)
	}
	if parsed.Scheme != "s3" || parsed.Host == "" {
		return DVCRemote{}, fmt.Errorf("DVC remote url must be s3://bucket/prefix")
	}
	remote.Bucket = parsed.Host
	remote.Prefix = strings.Trim(parsed.Path, "/")
	return remote, nil
}

func summarizeDVCLock(root string) (LockSummary, error) {
	path := filepath.Join(root, "dvc.lock")
	body, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return LockSummary{}, nil
		}
		return LockSummary{}, fmt.Errorf("read dvc.lock: %w", err)
	}
	text := string(body)
	summary := LockSummary{
		Present:        true,
		HasOutputHash:  strings.Contains(text, "md5:"),
		HasDependency:  strings.Contains(text, "deps:"),
		ContainsDVCOut: strings.Contains(text, "reports/generated/vton-catvton-2026-06-11-001"),
	}

	var inStages bool
	var inOuts bool
	scanner := bufio.NewScanner(strings.NewReader(text))
	for scanner.Scan() {
		raw := scanner.Text()
		trimmed := strings.TrimSpace(raw)
		if trimmed == "stages:" {
			inStages = true
			continue
		}
		if inStages && strings.HasPrefix(raw, "  ") && strings.HasSuffix(trimmed, ":") && !strings.HasPrefix(trimmed, "-") {
			stage := strings.TrimSuffix(trimmed, ":")
			if stage != "cmd" && stage != "deps" && stage != "outs" {
				summary.StageNames = append(summary.StageNames, stage)
			}
		}
		if trimmed == "outs:" {
			inOuts = true
			continue
		}
		if inOuts && strings.HasPrefix(trimmed, "- path:") {
			summary.OutputPaths = append(summary.OutputPaths, strings.TrimSpace(strings.TrimPrefix(trimmed, "- path:")))
		}
		if inOuts && trimmed == "deps:" {
			inOuts = false
		}
	}
	sort.Strings(summary.StageNames)
	sort.Strings(summary.OutputPaths)
	return summary, nil
}

func summarizeLocalCache(root string) (CacheSummary, error) {
	base := filepath.Join(root, ".dvc", "cache", "files", "md5")
	var summary CacheSummary
	err := filepath.WalkDir(base, func(path string, entry fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if entry.IsDir() {
			return nil
		}
		info, err := entry.Info()
		if err != nil {
			return err
		}
		rel, _ := filepath.Rel(root, path)
		summary.Count++
		summary.TotalBytes += info.Size()
		if len(summary.Samples) < 8 {
			summary.Samples = append(summary.Samples, filepath.ToSlash(rel))
		}
		return nil
	})
	if err != nil {
		if os.IsNotExist(err) {
			return summary, nil
		}
		return summary, fmt.Errorf("walk DVC cache: %w", err)
	}
	sort.Strings(summary.Samples)
	return summary, nil
}
