package main

import (
	"math"
	"sort"
	"time"
)

type tenantKey struct {
	Period   string
	UserHash string
}

func buildReadModel(input QuotaUsageReport, sourcePath string) Report {
	plans := inferPlans(input)
	grouped := map[tenantKey]map[string]uint64{}
	for _, row := range input.Snapshot.Usage {
		key := tenantKey{Period: row.Period, UserHash: row.UserHash}
		if _, ok := grouped[key]; !ok {
			grouped[key] = map[string]uint64{}
		}
		grouped[key][row.Dimension] += row.Used
	}

	tenants := make([]TenantReadModel, 0, len(grouped))
	for key, dimensions := range grouped {
		plan := plans[key.UserHash]
		if plan == "" {
			plan = input.Plan
		}
		if plan == "" {
			plan = "free"
		}
		tenants = append(tenants, buildTenant(key, plan, dimensions))
	}
	sort.Slice(tenants, func(i int, j int) bool {
		if tenants[i].Period == tenants[j].Period {
			return tenants[i].UserHash < tenants[j].UserHash
		}
		return tenants[i].Period < tenants[j].Period
	})
	periods := buildPeriods(tenants)
	summary := buildSummary(tenants, periods, input.NativeQuota.Available)
	checks := map[string]bool{
		"native_quota_source":       input.NativeQuota.Available || input.Snapshot.Engine == "native_rust_gateway",
		"hashed_tenant_only":        rawUserIDNotPresent(input),
		"tenant_read_model_present": len(tenants) > 0,
		"showback_present":          summary.ShowbackUSD >= 0,
		"limits_present":            summary.TotalLimit > 0,
	}
	passed := true
	for _, value := range checks {
		passed = passed && value
	}
	return Report{
		SchemaVersion: "tryops.native_quota_read_model.v1",
		GeneratedAt:   time.Now().UTC().Format(time.RFC3339),
		Passed:        passed,
		CoverageLevel: "native_quota_bff_showback_read_model",
		SourcePath:    sourcePath,
		SourceEngine:  sourceEngine(input),
		Research: []ResearchSource{
			{
				Name: "FinOps showback and allocation",
				URL:  "https://www.finops.org/framework/capabilities/allocation/",
				Use:  "tenant usage allocation and showback-style product read model",
			},
			{
				Name: "Valkey INCR/EXPIRE counters",
				URL:  "https://valkey.io/commands/incr/",
				Use:  "hot quota counters mirrored by the Rust gateway",
			},
			{
				Name: "PostgreSQL ON CONFLICT upserts",
				URL:  "https://www.postgresql.org/docs/current/sql-insert.html",
				Use:  "durable quota usage ledger upsert basis",
			},
		},
		Summary: summary,
		Periods: periods,
		Tenants: tenants,
		Checks:  checks,
	}
}

func buildTenant(key tenantKey, plan string, dimensions map[string]uint64) TenantReadModel {
	items := make([]DimensionReadModel, 0, len(dimensions))
	var totalUsed uint64
	var totalLimit uint64
	var showback float64
	for dimension, used := range dimensions {
		limit := limitFor(plan, dimension)
		remaining := limit
		if used < limit {
			remaining = limit - used
		} else {
			remaining = 0
		}
		unitPrice := unitPriceFor(dimension)
		itemShowback := round6(float64(used) * unitPrice)
		items = append(items, DimensionReadModel{
			Dimension:      dimension,
			Used:           used,
			Limit:          limit,
			Remaining:      remaining,
			UtilizationPct: utilization(used, limit),
			UnitPriceUSD:   unitPrice,
			ShowbackUSD:    itemShowback,
		})
		totalUsed += used
		totalLimit += limit
		showback += itemShowback
	}
	sort.Slice(items, func(i int, j int) bool {
		return items[i].Dimension < items[j].Dimension
	})
	return TenantReadModel{
		Period:         key.Period,
		UserHash:       key.UserHash,
		Plan:           plan,
		TotalUsed:      totalUsed,
		TotalLimit:     totalLimit,
		Remaining:      saturatingSub(totalLimit, totalUsed),
		UtilizationPct: utilization(totalUsed, totalLimit),
		ShowbackUSD:    round6(showback),
		Dimensions:     items,
		Risk:           riskFor(utilization(totalUsed, totalLimit)),
	}
}

func inferPlans(input QuotaUsageReport) map[string]string {
	plans := map[string]string{}
	for _, decision := range input.Decisions {
		if decision.UserHash != "" && decision.Plan != "" {
			plans[decision.UserHash] = decision.Plan
		}
	}
	return plans
}

func buildPeriods(tenants []TenantReadModel) []PeriodSummary {
	grouped := map[string]*PeriodSummary{}
	for _, tenant := range tenants {
		if _, ok := grouped[tenant.Period]; !ok {
			grouped[tenant.Period] = &PeriodSummary{Period: tenant.Period}
		}
		summary := grouped[tenant.Period]
		summary.Tenants++
		summary.TotalUsed += tenant.TotalUsed
		summary.ShowbackUSD = round6(summary.ShowbackUSD + tenant.ShowbackUSD)
	}
	periods := make([]PeriodSummary, 0, len(grouped))
	for _, summary := range grouped {
		periods = append(periods, *summary)
	}
	sort.Slice(periods, func(i int, j int) bool {
		return periods[i].Period < periods[j].Period
	})
	return periods
}

func buildSummary(tenants []TenantReadModel, periods []PeriodSummary, nativeSource bool) Summary {
	dimensions := map[string]bool{}
	var totalUsed uint64
	var totalLimit uint64
	var showback float64
	atRisk := 0
	for _, tenant := range tenants {
		totalUsed += tenant.TotalUsed
		totalLimit += tenant.TotalLimit
		showback += tenant.ShowbackUSD
		if tenant.Risk == "high" || tenant.Risk == "exhausted" {
			atRisk++
		}
		for _, dimension := range tenant.Dimensions {
			dimensions[dimension.Dimension] = true
		}
	}
	return Summary{
		Tenants:       len(tenants),
		Periods:       len(periods),
		Dimensions:    len(dimensions),
		TotalUsed:     totalUsed,
		TotalLimit:    totalLimit,
		ShowbackUSD:   round6(showback),
		NativeSource:  nativeSource,
		AtRiskTenants: atRisk,
	}
}

func utilization(used uint64, limit uint64) float64 {
	if limit == 0 {
		return 0
	}
	return round2(float64(used) * 100 / float64(limit))
}

func riskFor(utilizationPct float64) string {
	switch {
	case utilizationPct >= 100:
		return "exhausted"
	case utilizationPct >= 80:
		return "high"
	case utilizationPct >= 50:
		return "medium"
	default:
		return "low"
	}
}

func sourceEngine(input QuotaUsageReport) string {
	if input.NativeQuota.Engine != "" {
		return input.NativeQuota.Engine
	}
	if input.Snapshot.Engine != "" {
		return input.Snapshot.Engine
	}
	return "unknown"
}

func rawUserIDNotPresent(input QuotaUsageReport) bool {
	if input.UserID == "" {
		return true
	}
	for _, row := range input.Snapshot.Usage {
		if row.UserHash == input.UserID {
			return false
		}
	}
	return true
}

func saturatingSub(left uint64, right uint64) uint64 {
	if right > left {
		return 0
	}
	return left - right
}

func round2(value float64) float64 {
	return math.Round(value*100) / 100
}

func round6(value float64) float64 {
	return math.Round(value*1000000) / 1000000
}
