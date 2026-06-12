package main

func loadLLMTelemetry(benchmarkPath string, paretoPath string) (LLMTelemetry, error) {
	benchmarkData, err := readJSON(benchmarkPath)
	if err != nil {
		return LLMTelemetry{}, err
	}
	paretoData, err := readJSON(paretoPath)
	if err != nil {
		return LLMTelemetry{}, err
	}
	benchmark := benchmarkFromArtifact(benchmarkData)
	variants := variantsFromPareto(paretoData)
	bestTPS := benchmark.TokensPerSecond
	maxVRAM := 0.0
	nativeGateCount := 0
	for _, variant := range variants {
		if variant.TokensPerSecond > bestTPS {
			bestTPS = variant.TokensPerSecond
		}
		if variant.PeakVRAMGB > maxVRAM {
			maxVRAM = variant.PeakVRAMGB
		}
		if variant.NativeStatsPresent {
			nativeGateCount++
		}
	}
	return LLMTelemetry{
		Benchmark:          benchmark,
		Variants:           variants,
		BestTokensPerSec:   round6(bestTPS),
		MaxPeakVRAMGB:      round6(maxVRAM),
		VariantCount:       len(variants),
		NativeSLOGateCount: nativeGateCount,
	}, nil
}

func benchmarkFromArtifact(data map[string]interface{}) BenchmarkTelemetry {
	summary := objectField(data, "summary")
	phase := objectField(summary, "phase_timing")
	return BenchmarkTelemetry{
		Available:          numberField(summary, "tokens_per_second") > 0,
		TokensPerSecond:    round6(numberField(summary, "tokens_per_second")),
		MemoryGB:           round6(numberField(summary, "memory_gb")),
		LatencyP95MS:       round6(numberField(summary, "latency_p95_ms")),
		PhaseTimingPresent: boolFieldDefault(phase, "available", false),
	}
}

func variantsFromPareto(data map[string]interface{}) []VariantTelemetry {
	rows := arrayField(data, "variants")
	variants := make([]VariantTelemetry, 0, len(rows))
	for _, row := range rows {
		item, ok := row.(map[string]interface{})
		if !ok {
			continue
		}
		nativeStats := objectField(item, "native_perf_stats")
		slo := objectField(item, "slo")
		variants = append(variants, VariantTelemetry{
			Variant:            stringField(item, "variant"),
			Adapter:            stringField(item, "adapter"),
			Available:          boolFieldDefault(item, "available", false),
			TokensPerSecond:    round6(numberField(item, "tokens_per_second")),
			PeakVRAMGB:         round6(numberField(item, "peak_vram_gb")),
			LatencyP50MS:       round6(numberField(item, "latency_p50_ms")),
			NativeStatsPresent: boolFieldDefault(nativeStats, "available", false),
			SLOVerdict:         stringField(slo, "verdict"),
		})
	}
	return variants
}
