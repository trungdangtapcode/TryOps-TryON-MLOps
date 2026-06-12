package main

import "os/exec"

func discoverTools() []ToolStatus {
	tools := []ToolStatus{
		{Name: "docker", Required: true},
		{Name: "syft", Required: true},
		{Name: "trivy", Required: true},
		{Name: "cosign", Required: true},
		{Name: "go", Required: false},
		{Name: "cargo", Required: false},
		{Name: "npm", Required: false},
		{Name: "python", Required: false},
	}
	for i := range tools {
		path, err := exec.LookPath(tools[i].Name)
		if err == nil {
			tools[i].Path = path
			tools[i].Available = true
		}
	}
	return tools
}

func missingRequiredTools(tools []ToolStatus) []string {
	var missing []string
	for _, tool := range tools {
		if tool.Required && !tool.Available {
			missing = append(missing, tool.Name)
		}
	}
	return missing
}
