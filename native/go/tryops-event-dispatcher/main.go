package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"time"
)

func main() {
	cfg := parseConfig()
	ctx, cancel := context.WithTimeout(context.Background(), cfg.Timeout)
	defer cancel()

	summary := receiverSummary{}
	var receiver *sampleReceiver
	if cfg.Mode == "sample" {
		var err error
		receiver, err = startSampleReceiver(cfg.WebhookSecret)
		if err != nil {
			fmt.Fprintf(os.Stderr, "start receiver: %v\n", err)
			os.Exit(2)
		}
		defer receiver.close(context.Background())
		cfg.WebhookURL = receiver.url
	}

	events, err := readEvents(cfg.EventsPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "read events: %v\n", err)
		os.Exit(2)
	}
	client := &http.Client{Timeout: 5 * time.Second}
	results, err := dispatchEvents(ctx, client, cfg, events)
	if cfg.Mode == "sample" {
		// Give the local receiver a chance to update counters before report construction.
		time.Sleep(20 * time.Millisecond)
		if receiver != nil {
			summary = receiver.summary()
		}
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "dispatch events: %v\n", err)
	}
	report := buildReport(cfg.Mode, summary, results)
	printReport(report)
	if err := writeReport(cfg.OutputPath, report); err != nil {
		fmt.Fprintf(os.Stderr, "write report: %v\n", err)
		os.Exit(2)
	}
	encoded, _ := json.Marshal(report)
	fmt.Println(string(encoded))
	if err != nil || !report.Passed {
		os.Exit(1)
	}
}
