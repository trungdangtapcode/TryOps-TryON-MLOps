package main

import "path/filepath"

func buildOptimizationPanel(root string) *optimizationPanel {
	paretoPath := filepath.Join(root, "artifacts", "eval", "llm_pareto", "pareto.json")
	leaderboardPath := filepath.Join(root, "artifacts", "eval", "leaderboard", "leaderboard.json")
	energyPath := filepath.Join(root, "artifacts", "eval", "energy", "energy_sweep.json")
	pareto, paretoErr := readJSON(paretoPath)
	leaderboard, leaderboardErr := readJSON(leaderboardPath)
	energy, energyErr := readJSON(energyPath)
	if paretoErr != nil && leaderboardErr != nil && energyErr != nil {
		return nil
	}
	recommendation := objectField(pareto, "recommendation")
	carbonGate := objectField(energy, "carbon_gate")
	panel := &optimizationPanel{
		RecommendedVariant: stringField(recommendation, "variant"),
		Recommendation:     stringField(recommendation, "reason"),
		CarbonGateVerdict:  stringField(carbonGate, "verdict"),
		GreenestVariant:    stringField(carbonGate, "greenest_variant"),
		ModelID:            firstNonEmpty(stringField(pareto, "model_id"), stringField(energy, "model_id")),
		JudgeBackend:       stringField(leaderboard, "judge_backend"),
		Ranking:            stringArrayField(leaderboard, "ranking"),
		Sources: map[string]string{
			"pareto":      relPath(root, paretoPath),
			"leaderboard": relPath(root, leaderboardPath),
			"energy":      relPath(root, energyPath),
		},
	}
	frontier := stringSet(stringArrayField(pareto, "pareto_frontier"))
	variants := map[string]*optimizationVariant{}
	for _, item := range arrayField(pareto, "variants") {
		row, ok := item.(map[string]interface{})
		if !ok {
			continue
		}
		variantName := stringField(row, "variant")
		variant := ensureOptimizationVariant(variants, variantName)
		variant.Adapter = stringField(row, "adapter")
		copyNumber(&variant.QualityScore, row, "quality_score")
		copyNumber(&variant.LatencyP50MS, row, "latency_p50_ms")
		copyNumber(&variant.TokensPerSecond, row, "tokens_per_second")
		copyNumber(&variant.PeakVRAMGB, row, "peak_vram_gb")
		variant.SLOVerdict = stringField(objectField(row, "slo"), "verdict")
		variant.ParetoFrontier = frontier[variantName]
		variant.Recommended = variantName == panel.RecommendedVariant
	}
	for _, item := range arrayField(energy, "variants") {
		row, ok := item.(map[string]interface{})
		if !ok {
			continue
		}
		variant := ensureOptimizationVariant(variants, stringField(row, "variant"))
		copyNumber(&variant.EnergyWhPer1KTokens, row, "energy_wh_per_1k_tokens")
		copyNumber(&variant.SCIGPer1KTokens, row, "sci_g_per_1k_tokens")
	}
	for rank, name := range panel.Ranking {
		variant := ensureOptimizationVariant(variants, name)
		variant.LeaderboardRank = rank + 1
		for _, item := range arrayField(leaderboard, "leaderboard") {
			row, ok := item.(map[string]interface{})
			if !ok || stringField(row, "variant") != name {
				continue
			}
			copyNumber(&variant.QualityScore, row, "quality")
			copyNumber(&variant.LatencyP50MS, row, "latency_p50_ms")
			copyNumber(&variant.TokensPerSecond, row, "tokens_per_second")
			copyNumber(&variant.PeakVRAMGB, row, "peak_vram_gb")
			copyNumber(&variant.EnergyWhPer1KTokens, row, "energy_wh_per_1k_tokens")
			copyNumber(&variant.SCIGPer1KTokens, row, "sci_g_per_1k_tokens")
			if verdict := stringField(row, "slo_verdict"); verdict != "" {
				variant.SLOVerdict = verdict
			}
		}
	}
	for _, name := range orderedVariantNames(panel.Ranking, variants) {
		panel.Variants = append(panel.Variants, *variants[name])
	}
	return panel
}

func ensureOptimizationVariant(variants map[string]*optimizationVariant, name string) *optimizationVariant {
	if name == "" {
		name = "unknown"
	}
	if variants[name] == nil {
		variants[name] = &optimizationVariant{Variant: name}
	}
	return variants[name]
}

func copyNumber(target *float64, data map[string]interface{}, key string) {
	if value, ok := numberField(data, key); ok {
		*target = value
	}
}

func stringArrayField(data map[string]interface{}, key string) []string {
	var values []string
	for _, item := range arrayField(data, key) {
		if value, ok := item.(string); ok {
			values = append(values, value)
		}
	}
	return values
}

func stringSet(values []string) map[string]bool {
	set := map[string]bool{}
	for _, value := range values {
		set[value] = true
	}
	return set
}

func orderedVariantNames(ranking []string, variants map[string]*optimizationVariant) []string {
	seen := map[string]bool{}
	var names []string
	for _, name := range ranking {
		if variants[name] != nil {
			names = append(names, name)
			seen[name] = true
		}
	}
	for name := range variants {
		if !seen[name] {
			names = append(names, name)
		}
	}
	return names
}
