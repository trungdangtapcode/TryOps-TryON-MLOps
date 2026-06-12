package main

import (
	"os"
	"strings"
)

type DockerfileInfo struct {
	Path       string
	Present    bool
	FromLines  []string
	StageNames []string
	FinalBase  string
	Content    string
}

func readDockerfile(root string, path string) DockerfileInfo {
	info := DockerfileInfo{Path: path}
	content, err := os.ReadFile(resolve(root, path))
	if err != nil {
		return info
	}
	info.Present = true
	info.Content = string(content)
	for _, line := range strings.Split(info.Content, "\n") {
		trimmed := strings.TrimSpace(line)
		if !strings.HasPrefix(strings.ToUpper(trimmed), "FROM ") {
			continue
		}
		info.FromLines = append(info.FromLines, trimmed)
		parts := strings.Fields(trimmed)
		if len(parts) >= 2 {
			info.FinalBase = parts[1]
		}
		for index, part := range parts {
			if strings.EqualFold(part, "AS") && index+1 < len(parts) {
				info.StageNames = append(info.StageNames, parts[index+1])
			}
		}
	}
	return info
}

func dockerfileHasBuilder(info DockerfileInfo) bool {
	return len(info.StageNames) > 0 && len(info.FromLines) >= 2
}

func finalBaseIsNotBuilderSDK(info DockerfileInfo, forbidden []string) bool {
	base := strings.ToLower(info.FinalBase)
	for _, value := range forbidden {
		if strings.Contains(base, value) {
			return false
		}
	}
	return true
}

func containsAll(content string, needles []string) []string {
	missing := make([]string, 0)
	for _, needle := range needles {
		if !strings.Contains(content, needle) {
			missing = append(missing, needle)
		}
	}
	return missing
}
