package main

import (
	"context"
	"fmt"
)

func evaluateNativePolicyGate(data map[string]interface{}, targetStage string) (*NativePolicyResult, []string) {
	client := nativePolicyClientFromEnv()
	if !client.Enabled() {
		return nil, nil
	}
	value, ok := data["policy_candidate"]
	if !ok {
		value = data["candidate"]
	}
	if value == nil {
		result := NativePolicyResult{
			Available: true,
			CLIPath:   client.CLIPath,
			Error:     "policy_candidate is required when native policy CLI is configured",
		}
		return &result, []string{"reject: native C++ policy candidate is required"}
	}
	candidate, err := nativePolicyCandidateFromValue(value)
	if err != nil {
		result := NativePolicyResult{
			Available: true,
			CLIPath:   client.CLIPath,
			Error:     err.Error(),
		}
		return &result, []string{"reject: native C++ policy candidate invalid: " + err.Error()}
	}
	ctx, cancel := context.WithTimeout(context.Background(), client.Timeout)
	defer cancel()

	result, err := client.Evaluate(ctx, candidate, targetStage)
	if err != nil {
		return &result, []string{"reject: native C++ policy execution failed: " + err.Error()}
	}
	if !result.Decision.Approved {
		reason := "native C++ policy rejected candidate"
		if len(result.Decision.Reasons) > 0 {
			reason = fmt.Sprintf("%s: %s", reason, result.Decision.Reasons[0])
		}
		return &result, []string{"reject: " + reason}
	}
	return &result, nil
}
