package main

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestRunPreflightVerifiesGPTQAndAWQCandidates(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/test/gptq/resolve/main/config.json":
			writeJSON(w, map[string]interface{}{
				"model_type":    "qwen2",
				"architectures": []string{"Qwen2ForCausalLM"},
				"license":       "apache-2.0",
				"quantization_config": map[string]interface{}{
					"quant_method": "gptq",
					"bits":         4,
					"group_size":   128,
					"sym":          true,
				},
			})
		case "/test/awq/resolve/main/config.json":
			writeJSON(w, map[string]interface{}{
				"model_type":    "qwen2",
				"architectures": []string{"Qwen2ForCausalLM"},
				"license":       "apache-2.0",
				"quantization_config": map[string]interface{}{
					"quant_method": "awq",
					"bits":         4,
					"group_size":   128,
					"zero_point":   true,
					"version":      "gemm",
				},
			})
		case "/test/gptq/resolve/main/model.safetensors", "/test/awq/resolve/main/model.safetensors":
			w.Header().Set("Content-Length", "100")
			w.WriteHeader(http.StatusOK)
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	cfg := Config{
		BaseURL:        server.URL,
		OutputPath:     "unused.json",
		Python:         "python",
		Timeout:        5 * time.Second,
		RequestTimeout: 2 * time.Second,
		Candidates: []CandidateSpec{
			{Method: "gptq", Repo: "test/gptq"},
			{Method: "awq", Repo: "test/awq"},
		},
	}
	report := runPreflight(context.Background(), cfg)
	if report.Summary.SuitableCandidates != 2 {
		t.Fatalf("expected two suitable candidates, got %+v", report.Summary)
	}
	if report.Summary.GPTQStatus == "missing" || report.Summary.AWQStatus == "missing" {
		t.Fatalf("unexpected missing status: %+v", report.Summary)
	}
	for _, candidate := range report.Candidates {
		if !candidate.Suitable || !candidate.Reachable {
			t.Fatalf("candidate not suitable/reachable: %+v", candidate)
		}
		if candidate.Quantization.Bits != 4 || candidate.Quantization.GroupSize != 128 {
			t.Fatalf("unexpected quantization: %+v", candidate.Quantization)
		}
	}
}

func TestParseCandidates(t *testing.T) {
	got := parseCandidates("gptq=a/b, awq=c/d")
	if len(got) != 2 || got[0].Method != "gptq" || got[1].Repo != "c/d" {
		t.Fatalf("unexpected candidates: %+v", got)
	}
}

func writeJSON(w http.ResponseWriter, value map[string]interface{}) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(value)
}
