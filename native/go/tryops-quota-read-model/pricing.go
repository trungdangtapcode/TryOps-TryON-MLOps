package main

var planLimits = map[string]map[string]uint64{
	"free": {
		"llm_requests_per_day":  20,
		"llm_tokens_per_day":    5000,
		"vton_requests_per_day": 5,
	},
	"team": {
		"llm_requests_per_day":  500,
		"llm_tokens_per_day":    250000,
		"vton_requests_per_day": 100,
	},
	"enterprise": {
		"llm_requests_per_day":  50000,
		"llm_tokens_per_day":    25000000,
		"vton_requests_per_day": 10000,
	},
}

var unitPricesUSD = map[string]float64{
	"llm_requests_per_day":  0.0001,
	"llm_tokens_per_day":    0.0000002,
	"vton_requests_per_day": 0.0125,
}

func limitFor(plan string, dimension string) uint64 {
	if limits, ok := planLimits[plan]; ok {
		if limit, ok := limits[dimension]; ok {
			return limit
		}
	}
	return 0
}

func unitPriceFor(dimension string) float64 {
	return unitPricesUSD[dimension]
}
