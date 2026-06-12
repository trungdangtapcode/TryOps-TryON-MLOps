package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
	"time"
)

func newControllerServer() *http.Server {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", health)
	mux.HandleFunc("/reconcile", reconcile)
	mux.HandleFunc("/registry/webhook", registryWebhook)
	mux.HandleFunc("/github/pr-webhook", githubPRWebhook)
	mux.HandleFunc("/alerts/webhook", alertmanagerWebhook)

	return &http.Server{
		Addr:              getenv("TRYOPS_CONTROLLER_ADDR", ":8082"),
		Handler:           loggingMiddleware(mux),
		ReadHeaderTimeout: 5 * time.Second,
	}
}

func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		next.ServeHTTP(w, r)
		log.Printf("%s %s %s", r.Method, r.URL.Path, time.Since(start))
	})
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(payload); err != nil {
		log.Printf("write response: %v", err)
	}
}

func getenv(key, fallback string) string {
	value := os.Getenv(key)
	if value == "" {
		return fallback
	}
	return value
}
