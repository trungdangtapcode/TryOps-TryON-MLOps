package main

import "testing"

func TestBuildReadModelCreatesTenantShowback(t *testing.T) {
	input := QuotaUsageReport{
		UserID: "demo-user",
		Plan:   "free",
		NativeQuota: NativeQuotaInfo{
			Engine:    "native_rust_gateway",
			Available: true,
		},
		Decisions: []QuotaDecision{
			{UserHash: "tenant-a", Plan: "free"},
		},
		Snapshot: QuotaSnapshot{
			SchemaVersion: "tryops.quota_snapshot.v1",
			Engine:        "native_rust_gateway",
			Usage: []QuotaUsageRow{
				{Period: "2026-06-12", UserHash: "tenant-a", Dimension: "llm_requests_per_day", Used: 2},
				{Period: "2026-06-12", UserHash: "tenant-a", Dimension: "llm_tokens_per_day", Used: 300},
				{Period: "2026-06-12", UserHash: "tenant-a", Dimension: "vton_requests_per_day", Used: 1},
			},
		},
	}

	report := buildReadModel(input, "quota.json")

	if !report.Passed {
		t.Fatalf("expected report to pass: %#v", report.Checks)
	}
	if report.Summary.Tenants != 1 || report.Summary.Dimensions != 3 {
		t.Fatalf("unexpected summary: %#v", report.Summary)
	}
	if report.Tenants[0].ShowbackUSD <= 0 {
		t.Fatalf("expected positive showback: %#v", report.Tenants[0])
	}
	if !report.Checks["hashed_tenant_only"] {
		t.Fatalf("raw user id should not appear in snapshot")
	}
}

func TestBuildReadModelFailsWithoutNativeSource(t *testing.T) {
	report := buildReadModel(QuotaUsageReport{
		UserID: "demo-user",
		Plan:   "free",
		Snapshot: QuotaSnapshot{
			SchemaVersion: "tryops.quota_snapshot.v1",
			Usage: []QuotaUsageRow{
				{Period: "2026-06-12", UserHash: "tenant-a", Dimension: "llm_requests_per_day", Used: 1},
			},
		},
	}, "quota.json")

	if report.Passed {
		t.Fatalf("expected missing native source to fail")
	}
	if report.Checks["native_quota_source"] {
		t.Fatalf("native source check should fail")
	}
}
