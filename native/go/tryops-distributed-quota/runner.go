package main

import (
	"context"
	"sort"
	"sync"
)

func runDistributedQuota(ctx context.Context, cfg Config) []Attempt {
	client := newQuotaClient(cfg)
	request := QuotaRequest{
		UserID:          cfg.UserID,
		Plan:            cfg.Plan,
		Workload:        cfg.Workload,
		RequestUnits:    1,
		EstimatedTokens: cfg.EstimatedTokens,
		Period:          cfg.Period,
	}
	jobs := make(chan int)
	results := make(chan Attempt, cfg.Requests)
	workers := cfg.Concurrency
	if workers > cfg.Requests {
		workers = cfg.Requests
	}
	var group sync.WaitGroup
	for worker := 0; worker < workers; worker++ {
		group.Add(1)
		go func() {
			defer group.Done()
			for index := range jobs {
				gatewayURL := cfg.GatewayURLs[index%len(cfg.GatewayURLs)]
				status, decision, err := client.submit(ctx, gatewayURL, request)
				attempt := Attempt{
					Index:      index,
					GatewayURL: gatewayURL,
					StatusCode: status,
					Allowed:    decision.Allowed,
					Reason:     decision.Reason,
				}
				if err != nil {
					attempt.Error = err.Error()
				}
				results <- attempt
			}
		}()
	}
	for index := 0; index < cfg.Requests; index++ {
		jobs <- index
	}
	close(jobs)
	group.Wait()
	close(results)
	attempts := make([]Attempt, 0, cfg.Requests)
	for attempt := range results {
		attempts = append(attempts, attempt)
	}
	sort.Slice(attempts, func(left, right int) bool {
		return attempts[left].Index < attempts[right].Index
	})
	return attempts
}
