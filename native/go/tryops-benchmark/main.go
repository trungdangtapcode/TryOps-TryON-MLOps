package main

import (
	"flag"
	"fmt"
	"os"
)

func main() {
	config := BenchmarkConfig{}
	flag.IntVar(&config.Requests, "requests", 5000, "requests per benchmark scenario")
	flag.IntVar(&config.Concurrency, "concurrency", 32, "parallel workers per scenario")
	flag.StringVar(&config.GatewayBin, "gateway-bin", "../../../artifacts/native/tryops-gateway", "compiled Rust gateway binary")
	flag.StringVar(&config.PythonBin, "python-bin", "python", "Python executable used to start uvicorn")
	flag.IntVar(&config.GatewayPort, "gateway-port", 18191, "Rust gateway port")
	flag.IntVar(&config.PythonPort, "python-port", 18192, "FastAPI/uvicorn port")
	flag.StringVar(&config.Output, "output", "../../../artifacts/eval/gateway_benchmark/native_gateway_benchmark.json", "benchmark report path")
	flag.Parse()

	report, err := RunBenchmark(config)
	if err != nil {
		fmt.Fprintf(os.Stderr, "native gateway benchmark failed: %v\n", err)
		os.Exit(1)
	}
	if err := WriteReport(config.Output, report); err != nil {
		fmt.Fprintf(os.Stderr, "write native gateway benchmark report: %v\n", err)
		os.Exit(1)
	}
	PrintSummary(report)
}
