package main

import (
	"encoding/json"
	"fmt"
	"os"
)

func loadEnvelopes(path string) ([]Envelope, Source, error) {
	if path == "" {
		return sampleEnvelopes(), Source{Name: "builtin_samples", Present: true}, nil
	}
	content, err := os.ReadFile(path)
	if err != nil {
		return nil, Source{Name: "input", Path: path, Present: false}, err
	}
	var array []Envelope
	if err := json.Unmarshal(content, &array); err == nil {
		return array, Source{Name: "input", Path: path, Present: true}, nil
	}
	var object struct {
		Envelopes []Envelope `json:"envelopes"`
	}
	if err := json.Unmarshal(content, &object); err != nil {
		return nil, Source{Name: "input", Path: path, Present: true}, fmt.Errorf("parse envelopes: %w", err)
	}
	return object.Envelopes, Source{Name: "input", Path: path, Present: true}, nil
}
