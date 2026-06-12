package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os/exec"
	"time"
)

type NativePolicyClient struct {
	CLIPath string
	Timeout time.Duration
}

func nativePolicyClientFromEnv() NativePolicyClient {
	path := getenv("TRYOPS_CONTROLLER_POLICY_CLI", "")
	if path == "" {
		path = getenv("TRYOPS_NATIVE_POLICY_CLI", "")
	}
	return NativePolicyClient{
		CLIPath: path,
		Timeout: 5 * time.Second,
	}
}

func (client NativePolicyClient) Enabled() bool {
	return client.CLIPath != ""
}

func (client NativePolicyClient) Evaluate(
	ctx context.Context,
	candidate NativePolicyCandidate,
	targetStage string,
) (NativePolicyResult, error) {
	result := NativePolicyResult{
		Available:  true,
		CLIPath:    client.CLIPath,
		WireFormat: "tryops.native_policy.v1",
	}
	if !client.Enabled() {
		result.Available = false
		return result, fmt.Errorf("native policy CLI is not configured")
	}

	command := exec.CommandContext(ctx, client.CLIPath)
	command.Stdin = bytes.NewBufferString(renderNativePolicyWire(candidate, targetStage))
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	command.Stdout = &stdout
	command.Stderr = &stderr

	err := command.Run()
	if err != nil {
		var exitError *exec.ExitError
		if errors.As(err, &exitError) {
			result.ReturnCode = exitError.ExitCode()
			if result.ReturnCode != 2 {
				result.Error = stringsTrimFallback(stderr.String(), stdout.String())
				return result, fmt.Errorf("native policy CLI exited %d: %s", result.ReturnCode, result.Error)
			}
		} else {
			result.Error = err.Error()
			return result, err
		}
	}
	if result.ReturnCode == 0 && command.ProcessState != nil {
		result.ReturnCode = command.ProcessState.ExitCode()
	}
	if stdout.Len() == 0 {
		result.Error = stringsTrimFallback(stderr.String(), "empty native policy response")
		return result, errors.New(result.Error)
	}
	if decodeErr := json.Unmarshal(stdout.Bytes(), &result.Decision); decodeErr != nil {
		result.Error = decodeErr.Error()
		return result, fmt.Errorf("decode native policy response: %w", decodeErr)
	}
	return result, nil
}

func stringsTrimFallback(primary string, fallback string) string {
	if trimmed := trimSpace(primary); trimmed != "" {
		return trimmed
	}
	return trimSpace(fallback)
}

func trimSpace(value string) string {
	for len(value) > 0 && (value[0] == ' ' || value[0] == '\n' || value[0] == '\t' || value[0] == '\r') {
		value = value[1:]
	}
	for len(value) > 0 {
		last := value[len(value)-1]
		if last != ' ' && last != '\n' && last != '\t' && last != '\r' {
			break
		}
		value = value[:len(value)-1]
	}
	return value
}
