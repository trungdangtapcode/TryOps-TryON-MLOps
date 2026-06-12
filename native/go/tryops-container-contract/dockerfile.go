package main

import (
	"os"
	"strings"
)

type DockerfileInfo struct {
	Path       string
	Present    bool
	FromLines  []string
	BaseImages []string
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
		base := dockerFromBase(parts)
		if base != "" {
			info.BaseImages = append(info.BaseImages, base)
			info.FinalBase = base
		}
		for index, part := range parts {
			if strings.EqualFold(part, "AS") && index+1 < len(parts) {
				info.StageNames = append(info.StageNames, parts[index+1])
			}
		}
	}
	return info
}

func dockerFromBase(parts []string) string {
	for index := 1; index < len(parts); index++ {
		part := parts[index]
		if strings.HasPrefix(part, "--") {
			continue
		}
		if strings.EqualFold(part, "AS") {
			return ""
		}
		return part
	}
	return ""
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

func rustRuntimeABICheck(info DockerfileInfo) (bool, string) {
	rustBase := ""
	for _, base := range info.BaseImages {
		if strings.Contains(strings.ToLower(base), "rust:") {
			rustBase = base
			break
		}
	}
	if rustBase == "" {
		return true, "no rust builder stage"
	}
	builderSuite := debianSuite(rustBase)
	runtimeSuite := debianSuite(info.FinalBase)
	detail := "builder=" + rustBase + " runtime=" + info.FinalBase
	if builderSuite == "" {
		return false, detail + " builder_suite=unversioned"
	}
	if runtimeSuite == "" {
		return false, detail + " runtime_suite=unversioned"
	}
	if builderSuite != runtimeSuite {
		return false, detail + " builder_suite=" + builderSuite + " runtime_suite=" + runtimeSuite
	}
	return true, detail + " suite=" + builderSuite
}

func debianSuite(image string) string {
	lower := strings.ToLower(image)
	for _, suite := range []string{"bookworm", "bullseye", "trixie"} {
		if strings.Contains(lower, suite) {
			return suite
		}
	}
	if strings.Contains(lower, "alpine") {
		return "alpine"
	}
	return ""
}
