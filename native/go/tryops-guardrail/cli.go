package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
)

func runCLI() {
	payload, err := io.ReadAll(os.Stdin)
	if err != nil {
		fail("read stdin", err)
	}
	var request guardrailRequest
	if err := json.Unmarshal(payload, &request); err != nil {
		fail("parse JSON", err)
	}
	response := evaluate(request)
	encoded, err := json.MarshalIndent(response, "", "  ")
	if err != nil {
		fail("encode JSON", err)
	}
	fmt.Println(string(encoded))
}

func fail(context string, err error) {
	_ = json.NewEncoder(os.Stdout).Encode(map[string]any{
		"schema_version": schemaVersion,
		"status":         "error",
		"error":          fmt.Sprintf("%s: %v", context, err),
	})
	os.Exit(1)
}
