package main

func defaultPolicy() GatePolicy {
	healthSpeedup := 2.0
	promotionSpeedup := 2.0
	return GatePolicy{
		SchemaVersion: "tryops.native_slo_gate_policy.v1",
		Rules: []ScenarioPolicy{
			{
				Name:                 "gateway_health_native_latency",
				Scenario:             "health_get",
				Target:               "native_rust_gateway",
				MaxErrors:            0,
				MaxErrorRate:         0,
				MaxP95MS:             20,
				MaxP99MS:             35,
				MinRequestsPerSecond: 10000,
				CompareTarget:        "python_fastapi",
				RequiredSpeedup:      &healthSpeedup,
			},
			{
				Name:                 "promotion_native_direct_latency",
				Scenario:             "promotion_post_direct",
				Target:               "native_rust_gateway",
				MaxErrors:            0,
				MaxErrorRate:         0,
				MaxP95MS:             20,
				MaxP99MS:             35,
				MinRequestsPerSecond: 10000,
				CompareTarget:        "python_fastapi",
				RequiredSpeedup:      &promotionSpeedup,
			},
			{
				Name:                 "promotion_edge_proxy_overhead",
				Scenario:             "promotion_post_edge_proxy",
				Target:               "native_rust_gateway_proxy_to_fastapi",
				MaxErrors:            0,
				MaxErrorRate:         0,
				MaxP95MS:             150,
				MaxP99MS:             220,
				MinRequestsPerSecond: 400,
				CompareTarget:        "python_fastapi_direct",
				MinThroughputRatio:   0.75,
				MaxP95Ratio:          1.25,
				MaxP99Ratio:          1.25,
			},
		},
	}
}
