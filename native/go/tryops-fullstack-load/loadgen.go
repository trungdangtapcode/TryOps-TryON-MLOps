package main

import (
	"bytes"
	"io"
	"math"
	"net/http"
	"sort"
	"sync"
	"time"
)

func RunLoad(spec HTTPRequestSpec, totalRequests int, concurrency int) LoadResult {
	if totalRequests < 1 {
		totalRequests = 1
	}
	if concurrency < 1 {
		concurrency = 1
	}
	if concurrency > totalRequests {
		concurrency = totalRequests
	}
	perWorker := totalRequests / concurrency
	remainder := totalRequests % concurrency
	var mu sync.Mutex
	latencies := make([]float64, 0, totalRequests)
	errors := 0
	started := time.Now()
	var wg sync.WaitGroup
	for worker := 0; worker < concurrency; worker++ {
		count := perWorker
		if worker < remainder {
			count++
		}
		if count == 0 {
			continue
		}
		wg.Add(1)
		go func(workerCount int) {
			defer wg.Done()
			workerLatencies, workerErrors := runWorker(spec, workerCount)
			mu.Lock()
			latencies = append(latencies, workerLatencies...)
			errors += workerErrors
			mu.Unlock()
		}(count)
	}
	wg.Wait()
	elapsed := time.Since(started).Seconds()
	if elapsed <= 0 {
		elapsed = 0.000001
	}
	return summarize(latencies, elapsed, errors, totalRequests)
}

func runWorker(spec HTTPRequestSpec, count int) ([]float64, int) {
	transport := &http.Transport{
		MaxIdleConns:        2,
		MaxIdleConnsPerHost: 2,
		IdleConnTimeout:     30 * time.Second,
		DisableCompression:  true,
	}
	client := &http.Client{Timeout: 10 * time.Second, Transport: transport}
	defer transport.CloseIdleConnections()
	latencies := make([]float64, 0, count)
	errors := 0
	for i := 0; i < count; i++ {
		started := time.Now()
		req, err := http.NewRequest(spec.Method, spec.URL, bytes.NewReader(spec.Body))
		if err != nil {
			errors++
			continue
		}
		for key, value := range spec.Headers {
			req.Header.Set(key, value)
		}
		resp, err := client.Do(req)
		if err != nil {
			errors++
			continue
		}
		_, _ = io.Copy(io.Discard, resp.Body)
		_ = resp.Body.Close()
		if resp.StatusCode != spec.ExpectedStatus {
			errors++
			continue
		}
		latencies = append(latencies, float64(time.Since(started).Microseconds())/1000.0)
	}
	return latencies, errors
}

func summarize(latencies []float64, elapsedSeconds float64, errors int, total int) LoadResult {
	sort.Float64s(latencies)
	latency := LatencySummary{}
	if len(latencies) > 0 {
		sum := 0.0
		for _, value := range latencies {
			sum += value
		}
		latency = LatencySummary{
			P50:  round4(percentile(latencies, 0.50)),
			P95:  round4(percentile(latencies, 0.95)),
			P99:  round4(percentile(latencies, 0.99)),
			Min:  round4(latencies[0]),
			Max:  round4(latencies[len(latencies)-1]),
			Mean: round4(sum / float64(len(latencies))),
		}
	}
	return LoadResult{
		Requests:       total,
		Errors:         errors,
		ErrorRate:      round6(float64(errors) / float64(total)),
		ElapsedSeconds: round6(elapsedSeconds),
		RequestsPerSec: round2(float64(total) / elapsedSeconds),
		LatencyMs:      latency,
	}
}

func percentile(sorted []float64, q float64) float64 {
	if len(sorted) == 0 {
		return 0
	}
	index := int(math.Round(float64(len(sorted)-1) * q))
	if index < 0 {
		index = 0
	}
	if index >= len(sorted) {
		index = len(sorted) - 1
	}
	return sorted[index]
}

func round2(value float64) float64 {
	return math.Round(value*100) / 100
}

func round4(value float64) float64 {
	return math.Round(value*10000) / 10000
}

func round6(value float64) float64 {
	return math.Round(value*1000000) / 1000000
}
