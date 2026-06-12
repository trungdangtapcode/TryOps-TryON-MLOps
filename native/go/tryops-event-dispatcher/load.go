package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"strings"
)

func readEvents(path string) ([]Event, error) {
	if strings.TrimSpace(path) == "" {
		return sampleEvents(), nil
	}
	payload, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	trimmed := bytes.TrimSpace(payload)
	if len(trimmed) == 0 {
		return nil, fmt.Errorf("events file is empty")
	}
	if trimmed[0] == '[' {
		var events []Event
		if err := json.Unmarshal(trimmed, &events); err != nil {
			return nil, err
		}
		return events, nil
	}
	return readJSONLines(trimmed)
}

func readJSONLines(payload []byte) ([]Event, error) {
	scanner := bufio.NewScanner(bytes.NewReader(payload))
	events := []Event{}
	lineNumber := 0
	for scanner.Scan() {
		lineNumber++
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var event Event
		if err := json.Unmarshal([]byte(line), &event); err != nil {
			return nil, fmt.Errorf("line %d: %w", lineNumber, err)
		}
		events = append(events, event)
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	return events, nil
}
