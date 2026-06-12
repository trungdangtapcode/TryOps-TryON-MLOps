package main

import "os/exec"

func detectExternalTools(requireExternal bool) []ExternalTool {
	tools := []ExternalTool{
		detectTool("k6", requireExternal),
		detectTool("locust", requireExternal),
	}
	if !tools[0].Available && !tools[1].Available {
		for i := range tools {
			tools[i].Note = "not installed locally; native Go driver remains the executed load gate"
		}
	}
	return tools
}

func detectTool(name string, required bool) ExternalTool {
	path, err := exec.LookPath(name)
	return ExternalTool{
		Name:      name,
		Required:  required,
		Available: err == nil,
		Path:      path,
	}
}

func externalAvailable(tools []ExternalTool) bool {
	for _, tool := range tools {
		if tool.Available {
			return true
		}
	}
	return false
}

func externalGatePassed(tools []ExternalTool) bool {
	if externalAvailable(tools) {
		return true
	}
	for _, tool := range tools {
		if tool.Required {
			return false
		}
	}
	return true
}
