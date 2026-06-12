package main

import (
	"context"
	"encoding/json"
	"io"
	"net"
	"net/http"
	"sync"
)

type sampleReceiver struct {
	server   *http.Server
	url      string
	secret   string
	mu       sync.Mutex
	accepted int
	rejected int
}

func startSampleReceiver(secret string) (*sampleReceiver, error) {
	receiver := &sampleReceiver{secret: secret}
	mux := http.NewServeMux()
	mux.HandleFunc("/events", receiver.handle)
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return nil, err
	}
	receiver.url = "http://" + listener.Addr().String() + "/events"
	receiver.server = &http.Server{Handler: mux}
	go receiver.server.Serve(listener)
	return receiver, nil
}

func (receiver *sampleReceiver) close(ctx context.Context) {
	if receiver.server != nil {
		receiver.server.Shutdown(ctx)
	}
}

func (receiver *sampleReceiver) summary() receiverSummary {
	receiver.mu.Lock()
	defer receiver.mu.Unlock()
	return receiverSummary{Enabled: true, AcceptedEvents: receiver.accepted, RejectedEvents: receiver.rejected}
}

func (receiver *sampleReceiver) handle(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(io.LimitReader(r.Body, 1024*1024))
	if err != nil {
		receiver.reject(w)
		return
	}
	timestamp := r.Header.Get("X-TryOps-Webhook-Timestamp")
	signature := r.Header.Get("X-TryOps-Signature-256")
	var event Event
	if err := json.Unmarshal(body, &event); err != nil || !verifySignature(receiver.secret, timestamp, body, signature) {
		receiver.reject(w)
		return
	}
	receiver.mu.Lock()
	receiver.accepted++
	receiver.mu.Unlock()
	w.WriteHeader(http.StatusAccepted)
	w.Write([]byte(`{"status":"accepted"}`))
}

func (receiver *sampleReceiver) reject(w http.ResponseWriter) {
	receiver.mu.Lock()
	receiver.rejected++
	receiver.mu.Unlock()
	http.Error(w, "rejected", http.StatusUnauthorized)
}
