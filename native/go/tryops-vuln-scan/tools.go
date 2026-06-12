package main

import "os/exec"

func discoverTools() []toolStatus {
	specs := []toolStatus{
		{Name: "trivy", Required: true},
		{Name: "syft", Required: true},
		{Name: "grype", Required: true},
		{Name: "pip-audit", Required: true},
		{Name: "gitleaks", Required: true},
		{Name: "osv-scanner", Required: true},
		{Name: "govulncheck", Required: false},
		{Name: "cargo-audit", Required: false},
		{Name: "cosign", Required: true},
		{Name: "npm", Required: false},
		{Name: "go", Required: false},
	}
	for i := range specs {
		path, err := exec.LookPath(specs[i].Name)
		if err == nil {
			specs[i].Path = path
			specs[i].Available = true
		}
	}
	return specs
}

func missingRequiredTools(tools []toolStatus) []string {
	var missing []string
	for _, tool := range tools {
		if tool.Required && !tool.Available {
			missing = append(missing, tool.Name)
		}
	}
	return missing
}

func toolAvailable(tools []toolStatus, name string) bool {
	for _, tool := range tools {
		if tool.Name == name {
			return tool.Available
		}
	}
	return false
}
