package main

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

var requiredRoles = []string{"gateway", "controller", "guardrail", "benchmark", "cpp-tools", "api", "web-assets"}

func evaluate(root string, manifest Manifest, compose ComposeFile, manifestPath string, composePath string) Report {
	checks := make([]Check, 0)
	imagesByRole := map[string]ImageSpec{}
	for _, image := range manifest.Images {
		imagesByRole[image.Role] = image
	}
	composeMatchedRoles := 0
	for _, role := range requiredRoles {
		image, ok := imagesByRole[role]
		checks = append(checks, Check{
			Name:   "manifest_has_role_" + role,
			Passed: ok,
			Detail: role,
		})
		if !ok {
			continue
		}
		checks = append(checks, validateImageSpec(root, image)...)
		service, serviceOK := compose.Services[image.ComposeService]
		if serviceOK {
			composeMatchedRoles++
		}
		checks = append(checks, validateComposeService(image, service, serviceOK)...)
	}
	checks = append(checks, Check{
		Name:   "manifest_schema",
		Passed: manifest.SchemaVersion == "tryops.container_images.v1",
		Detail: manifest.SchemaVersion,
	})
	checks = append(checks, uniqueRoles(manifest.Images))
	checks = append(checks, Check{
		Name:   "compose_has_services",
		Passed: len(compose.Services) > 0,
		Detail: fmt.Sprintf("%d services", len(compose.Services)),
	})

	passedChecks := 0
	failedChecks := 0
	for _, check := range checks {
		if check.Passed {
			passedChecks++
		} else {
			failedChecks++
		}
	}
	return Report{
		SchemaVersion: "tryops.native_container_contract.v1",
		GeneratedAt:   nowUTC(),
		Passed:        failedChecks == 0,
		CoverageLevel: "native_container_image_split_contract",
		Manifest:      manifestPath,
		Compose:       composePath,
		Research: []ResearchSource{
			{
				Name: "Docker multi-stage builds",
				URL:  "https://docs.docker.com/build/building/multi-stage/",
				Use:  "separate compiler/build stages from smaller runtime images",
			},
			{
				Name: "Docker Compose build specification",
				URL:  "https://docs.docker.com/compose/compose-file/build/",
				Use:  "explicit service build contexts and Dockerfile paths",
			},
			{
				Name: "Docker Buildx metadata/provenance",
				URL:  "https://docs.docker.com/build/metadata/",
				Use:  "future CI artifact metadata, digest, SBOM, and provenance capture",
			},
		},
		Summary: Summary{
			RequiredRoles: len(requiredRoles),
			ManifestRoles: len(imagesByRole),
			ComposeRoles:  composeMatchedRoles,
			PassedChecks:  passedChecks,
			FailedChecks:  failedChecks,
			ByRuntime:     countByRuntime(manifest.Images),
		},
		Checks: checks,
		Images: manifest.Images,
	}
}

func validateImageSpec(root string, image ImageSpec) []Check {
	checks := []Check{}
	info := readDockerfile(root, image.Dockerfile)
	checks = append(checks, Check{
		Name:   image.Role + "_dockerfile_exists",
		Passed: info.Present,
		Detail: image.Dockerfile,
	})
	if !info.Present {
		return checks
	}
	checks = append(checks, Check{
		Name:   image.Role + "_dockerfile_has_from",
		Passed: len(info.FromLines) > 0,
		Detail: strings.Join(info.FromLines, " | "),
	})
	if image.RequiredStage != "python" {
		checks = append(checks, Check{
			Name:   image.Role + "_uses_multistage_build",
			Passed: dockerfileHasBuilder(info),
			Detail: fmt.Sprintf("stages=%v", info.StageNames),
		})
	}
	switch image.RequiredStage {
	case "go":
		checks = append(checks, Check{
			Name:   image.Role + "_builds_with_go",
			Passed: strings.Contains(strings.ToLower(info.Content), "golang:"),
			Detail: image.Dockerfile,
		})
		checks = append(checks, Check{
			Name:   image.Role + "_runtime_not_go_sdk",
			Passed: finalBaseIsNotBuilderSDK(info, []string{"golang"}),
			Detail: info.FinalBase,
		})
	case "rust":
		checks = append(checks, Check{
			Name:   image.Role + "_builds_with_rust",
			Passed: strings.Contains(strings.ToLower(info.Content), "rust:"),
			Detail: image.Dockerfile,
		})
		checks = append(checks, Check{
			Name:   image.Role + "_runtime_not_rust_sdk",
			Passed: finalBaseIsNotBuilderSDK(info, []string{"rust"}),
			Detail: info.FinalBase,
		})
	case "cpp":
		checks = append(checks, Check{
			Name:   image.Role + "_builds_with_cpp_compiler",
			Passed: strings.Contains(strings.ToLower(info.Content), "gcc:") || strings.Contains(info.Content, "g++"),
			Detail: image.Dockerfile,
		})
		checks = append(checks, Check{
			Name:   image.Role + "_runtime_not_cpp_sdk",
			Passed: finalBaseIsNotBuilderSDK(info, []string{"gcc"}),
			Detail: info.FinalBase,
		})
	case "node":
		checks = append(checks, Check{
			Name:   image.Role + "_builds_with_node",
			Passed: strings.Contains(strings.ToLower(info.Content), "node:") && strings.Contains(info.Content, "npm run build"),
			Detail: image.Dockerfile,
		})
		checks = append(checks, Check{
			Name:   image.Role + "_runtime_not_node_sdk",
			Passed: finalBaseIsNotBuilderSDK(info, []string{"node"}),
			Detail: info.FinalBase,
		})
	case "python":
		checks = append(checks, Check{
			Name:   image.Role + "_uses_python_runtime",
			Passed: strings.Contains(strings.ToLower(info.FinalBase), "python:"),
			Detail: info.FinalBase,
		})
	}
	missingSources := missingSourcePaths(root, image.SourcePaths)
	checks = append(checks, Check{
		Name:   image.Role + "_source_paths_exist",
		Passed: len(missingSources) == 0,
		Detail: strings.Join(missingSources, ","),
	})
	missingCopies := copiedSourcePathHints(info.Content, image.SourcePaths)
	checks = append(checks, Check{
		Name:   image.Role + "_dockerfile_copies_declared_sources",
		Passed: len(missingCopies) == 0,
		Detail: strings.Join(missingCopies, ","),
	})
	return checks
}

func validateComposeService(image ImageSpec, service ComposeService, serviceOK bool) []Check {
	checks := []Check{{
		Name:   image.Role + "_compose_service_exists",
		Passed: serviceOK,
		Detail: image.ComposeService,
	}}
	if !serviceOK {
		return checks
	}
	dockerfile := fmt.Sprint(service.Build["dockerfile"])
	context := fmt.Sprint(service.Build["context"])
	checks = append(checks, Check{
		Name:   image.Role + "_compose_dockerfile_matches",
		Passed: dockerfile == image.Dockerfile,
		Detail: dockerfile,
	})
	checks = append(checks, Check{
		Name:   image.Role + "_compose_context_matches",
		Passed: context == image.Context,
		Detail: context,
	})
	if len(image.Ports) > 0 {
		checks = append(checks, Check{
			Name:   image.Role + "_compose_exposes_port",
			Passed: len(service.Ports) > 0,
			Detail: fmt.Sprintf("%v", service.Ports),
		})
	}
	if optionalImageRole(image.Role) {
		checks = append(checks, Check{
			Name:   image.Role + "_compose_uses_profile",
			Passed: len(service.Profiles) > 0,
			Detail: strings.Join(service.Profiles, ","),
		})
	}
	return checks
}

func optionalImageRole(role string) bool {
	return role == "controller" || role == "benchmark" || role == "cpp-tools" || role == "web-assets"
}

func missingSourcePaths(root string, paths []string) []string {
	missing := []string{}
	for _, path := range paths {
		if _, err := os.Stat(resolve(root, path)); err != nil {
			missing = append(missing, path)
		}
	}
	return missing
}

func copiedSourcePathHints(content string, paths []string) []string {
	missing := []string{}
	for _, path := range paths {
		hint := firstPathSegment(path)
		if hint == "" || strings.Contains(content, hint) {
			continue
		}
		missing = append(missing, hint)
	}
	return uniqueStrings(missing)
}

func firstPathSegment(path string) string {
	clean := filepath.ToSlash(path)
	parts := strings.Split(clean, "/")
	if len(parts) == 0 {
		return ""
	}
	return parts[0]
}

func uniqueRoles(images []ImageSpec) Check {
	seen := map[string]bool{}
	duplicates := []string{}
	for _, image := range images {
		if seen[image.Role] {
			duplicates = append(duplicates, image.Role)
		}
		seen[image.Role] = true
	}
	return Check{
		Name:   "manifest_roles_unique",
		Passed: len(duplicates) == 0,
		Detail: strings.Join(duplicates, ","),
	}
}

func countByRuntime(images []ImageSpec) map[string]int {
	counts := map[string]int{}
	for _, image := range images {
		counts[image.RequiredStage]++
	}
	return counts
}

func uniqueStrings(values []string) []string {
	seen := map[string]bool{}
	unique := []string{}
	for _, value := range values {
		if seen[value] {
			continue
		}
		seen[value] = true
		unique = append(unique, value)
	}
	sort.Strings(unique)
	return unique
}
