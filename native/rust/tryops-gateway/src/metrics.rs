use std::collections::HashMap;

use axum::http::Uri;

#[derive(Debug, Default)]
pub(crate) struct MetricsLedger {
    requests: HashMap<(String, String, String), u64>,
    latency_buckets: HashMap<(String, String, String, String), u64>,
    latency_sum_ms: HashMap<(String, String, String), f64>,
    latency_count: HashMap<(String, String, String), u64>,
    auth_decisions: HashMap<(String, String, String), u64>,
    quota_decisions: HashMap<(String, String, String), u64>,
    guardrail_decisions: HashMap<String, u64>,
    semantic_cache_admissions: HashMap<(String, String), u64>,
    semantic_cache_lookups: HashMap<(String, String), u64>,
    rate_limited_total: u64,
    upstream_errors: HashMap<(String, String), u64>,
    proxy_inflight: u64,
}

const LATENCY_BUCKETS_MS: [f64; 8] = [1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 1000.0];

impl MetricsLedger {
    pub(crate) fn record_request(
        &mut self,
        route: &str,
        method: &str,
        status: u16,
        latency_ms: f64,
    ) {
        let status_label = status.to_string();
        let key = (route.to_string(), method.to_string(), status_label);
        *self.requests.entry(key.clone()).or_insert(0) += 1;
        *self.latency_sum_ms.entry(key.clone()).or_insert(0.0) += latency_ms;
        *self.latency_count.entry(key.clone()).or_insert(0) += 1;
        for bucket in LATENCY_BUCKETS_MS {
            if latency_ms <= bucket {
                *self
                    .latency_buckets
                    .entry((
                        key.0.clone(),
                        key.1.clone(),
                        key.2.clone(),
                        bucket_label(bucket),
                    ))
                    .or_insert(0) += 1;
            }
        }
    }

    pub(crate) fn record_quota_decision(&mut self, allowed: bool, workload: &str, plan: &str) {
        *self
            .quota_decisions
            .entry((allowed.to_string(), workload.to_string(), plan.to_string()))
            .or_insert(0) += 1;
    }

    pub(crate) fn record_auth_decision(
        &mut self,
        allowed: bool,
        reason: &str,
        required_scope: &str,
    ) {
        *self
            .auth_decisions
            .entry((
                allowed.to_string(),
                reason.to_string(),
                required_scope.to_string(),
            ))
            .or_insert(0) += 1;
    }

    pub(crate) fn record_guardrail_decision(&mut self, status: &str) {
        *self
            .guardrail_decisions
            .entry(status.to_string())
            .or_insert(0) += 1;
    }

    pub(crate) fn record_semantic_cache_admission(&mut self, admitted: bool, reason: &str) {
        *self
            .semantic_cache_admissions
            .entry((admitted.to_string(), reason.to_string()))
            .or_insert(0) += 1;
    }

    pub(crate) fn record_semantic_cache_lookup(&mut self, source: &str, result: &str) {
        *self
            .semantic_cache_lookups
            .entry((source.to_string(), result.to_string()))
            .or_insert(0) += 1;
    }

    pub(crate) fn record_rate_limited(&mut self) {
        self.rate_limited_total = self.rate_limited_total.saturating_add(1);
    }

    pub(crate) fn record_upstream_error(&mut self, route: &str, method: &str) {
        *self
            .upstream_errors
            .entry((route.to_string(), method.to_string()))
            .or_insert(0) += 1;
    }

    pub(crate) fn record_proxy_inflight_delta(&mut self, delta: i64) {
        if delta.is_negative() {
            self.proxy_inflight = self.proxy_inflight.saturating_sub(delta.unsigned_abs());
        } else {
            self.proxy_inflight = self.proxy_inflight.saturating_add(delta as u64);
        }
    }

    pub(crate) fn render(&self) -> String {
        let mut lines = vec![
            "# HELP tryops_gateway_requests_total Total requests handled by the native Rust gateway.".to_string(),
            "# TYPE tryops_gateway_requests_total counter".to_string(),
        ];

        let mut request_rows = self.requests.iter().collect::<Vec<_>>();
        request_rows.sort_by(|left, right| left.0.cmp(right.0));
        for ((route, method, status), value) in request_rows {
            lines.push(format!(
                "tryops_gateway_requests_total{{route=\"{}\",method=\"{}\",status=\"{}\"}} {}",
                escape_label(route),
                escape_label(method),
                escape_label(status),
                value
            ));
        }

        lines.push("# HELP tryops_gateway_request_latency_ms Native gateway request latency histogram in milliseconds.".to_string());
        lines.push("# TYPE tryops_gateway_request_latency_ms histogram".to_string());
        let mut latency_keys = self.latency_count.keys().collect::<Vec<_>>();
        latency_keys.sort();
        for (route, method, status) in latency_keys {
            for bucket in LATENCY_BUCKETS_MS {
                let le = bucket_label(bucket);
                let value = self
                    .latency_buckets
                    .get(&(route.clone(), method.clone(), status.clone(), le.clone()))
                    .copied()
                    .unwrap_or(0);
                lines.push(format!(
                    "tryops_gateway_request_latency_ms_bucket{{route=\"{}\",method=\"{}\",status=\"{}\",le=\"{}\"}} {}",
                    escape_label(route),
                    escape_label(method),
                    escape_label(status),
                    le,
                    value
                ));
            }
            let count = self
                .latency_count
                .get(&(route.clone(), method.clone(), status.clone()))
                .copied()
                .unwrap_or(0);
            let sum = self
                .latency_sum_ms
                .get(&(route.clone(), method.clone(), status.clone()))
                .copied()
                .unwrap_or(0.0);
            lines.push(format!(
                "tryops_gateway_request_latency_ms_bucket{{route=\"{}\",method=\"{}\",status=\"{}\",le=\"+Inf\"}} {}",
                escape_label(route),
                escape_label(method),
                escape_label(status),
                count
            ));
            lines.push(format!(
                "tryops_gateway_request_latency_ms_sum{{route=\"{}\",method=\"{}\",status=\"{}\"}} {:.6}",
                escape_label(route),
                escape_label(method),
                escape_label(status),
                sum
            ));
            lines.push(format!(
                "tryops_gateway_request_latency_ms_count{{route=\"{}\",method=\"{}\",status=\"{}\"}} {}",
                escape_label(route),
                escape_label(method),
                escape_label(status),
                count
            ));
        }

        lines.push("# HELP tryops_gateway_quota_decisions_total Native quota decisions by workload and plan.".to_string());
        lines.push("# TYPE tryops_gateway_quota_decisions_total counter".to_string());
        let mut quota_rows = self.quota_decisions.iter().collect::<Vec<_>>();
        quota_rows.sort_by(|left, right| left.0.cmp(right.0));
        for ((allowed, workload, plan), value) in quota_rows {
            lines.push(format!(
                "tryops_gateway_quota_decisions_total{{allowed=\"{}\",workload=\"{}\",plan=\"{}\"}} {}",
                escape_label(allowed),
                escape_label(workload),
                escape_label(plan),
                value
            ));
        }

        lines.push("# HELP tryops_gateway_auth_decisions_total Native edge auth decisions by required scope and reason.".to_string());
        lines.push("# TYPE tryops_gateway_auth_decisions_total counter".to_string());
        let mut auth_rows = self.auth_decisions.iter().collect::<Vec<_>>();
        auth_rows.sort_by(|left, right| left.0.cmp(right.0));
        for ((allowed, reason, required_scope), value) in auth_rows {
            lines.push(format!(
                "tryops_gateway_auth_decisions_total{{allowed=\"{}\",reason=\"{}\",required_scope=\"{}\"}} {}",
                escape_label(allowed),
                escape_label(reason),
                escape_label(required_scope),
                value
            ));
        }

        lines.push("# HELP tryops_gateway_guardrail_decisions_total LLM edge guardrail decisions made by the native gateway.".to_string());
        lines.push("# TYPE tryops_gateway_guardrail_decisions_total counter".to_string());
        let mut guardrail_rows = self.guardrail_decisions.iter().collect::<Vec<_>>();
        guardrail_rows.sort_by(|left, right| left.0.cmp(right.0));
        for (status, value) in guardrail_rows {
            lines.push(format!(
                "tryops_gateway_guardrail_decisions_total{{status=\"{}\"}} {}",
                escape_label(status),
                value
            ));
        }

        lines.push("# HELP tryops_gateway_semantic_cache_admissions_total Native edge semantic-cache admission decisions before API proxy.".to_string());
        lines.push("# TYPE tryops_gateway_semantic_cache_admissions_total counter".to_string());
        let mut semantic_cache_rows = self.semantic_cache_admissions.iter().collect::<Vec<_>>();
        semantic_cache_rows.sort_by(|left, right| left.0.cmp(right.0));
        for ((admitted, reason), value) in semantic_cache_rows {
            lines.push(format!(
                "tryops_gateway_semantic_cache_admissions_total{{admitted=\"{}\",reason=\"{}\"}} {}",
                escape_label(admitted),
                escape_label(reason),
                value
            ));
        }

        lines.push("# HELP tryops_gateway_semantic_cache_lookups_total Native edge semantic-cache vector lookups before API proxy.".to_string());
        lines.push("# TYPE tryops_gateway_semantic_cache_lookups_total counter".to_string());
        let mut semantic_lookup_rows = self.semantic_cache_lookups.iter().collect::<Vec<_>>();
        semantic_lookup_rows.sort_by(|left, right| left.0.cmp(right.0));
        for ((source, result), value) in semantic_lookup_rows {
            lines.push(format!(
                "tryops_gateway_semantic_cache_lookups_total{{source=\"{}\",result=\"{}\"}} {}",
                escape_label(source),
                escape_label(result),
                value
            ));
        }

        lines.push("# HELP tryops_gateway_rate_limited_total Requests rejected by the native gateway rate limiter.".to_string());
        lines.push("# TYPE tryops_gateway_rate_limited_total counter".to_string());
        lines.push(format!(
            "tryops_gateway_rate_limited_total {}",
            self.rate_limited_total
        ));

        lines.push("# HELP tryops_gateway_upstream_errors_total Upstream proxy failures observed by the native gateway.".to_string());
        lines.push("# TYPE tryops_gateway_upstream_errors_total counter".to_string());
        let mut upstream_rows = self.upstream_errors.iter().collect::<Vec<_>>();
        upstream_rows.sort_by(|left, right| left.0.cmp(right.0));
        for ((route, method), value) in upstream_rows {
            lines.push(format!(
                "tryops_gateway_upstream_errors_total{{route=\"{}\",method=\"{}\"}} {}",
                escape_label(route),
                escape_label(method),
                value
            ));
        }

        lines.push(
            "# HELP tryops_gateway_proxy_inflight Current proxied requests in flight.".to_string(),
        );
        lines.push("# TYPE tryops_gateway_proxy_inflight gauge".to_string());
        lines.push(format!(
            "tryops_gateway_proxy_inflight {}",
            self.proxy_inflight
        ));
        lines.push(String::new());
        lines.join("\n")
    }
}

pub(crate) fn gateway_route_label(uri: &Uri) -> String {
    let path = uri.path();
    if path == "/api" {
        return "/api".to_string();
    }
    if path.starts_with("/api/llm/") {
        return "/api/llm/*".to_string();
    }
    if path.starts_with("/api/vton/") {
        return "/api/vton/*".to_string();
    }
    if path.starts_with("/api/promotion/") {
        return "/api/promotion/*".to_string();
    }
    if path.starts_with("/api/models/") {
        return "/api/models/*".to_string();
    }
    if path.starts_with("/api/") {
        return "/api/*".to_string();
    }
    path.to_string()
}

fn escape_label(value: &str) -> String {
    value
        .replace('\\', "\\\\")
        .replace('\n', "\\n")
        .replace('"', "\\\"")
}

fn bucket_label(bucket: f64) -> String {
    if bucket.fract() == 0.0 {
        format!("{bucket:.0}")
    } else {
        bucket.to_string()
    }
}

#[cfg(test)]
mod tests {
    use axum::http::Uri;

    use super::*;

    #[test]
    fn gateway_metrics_render_counter_histogram_and_quota_decision() {
        let mut metrics = MetricsLedger::default();
        metrics.record_request("/api/llm/*", "POST", 200, 12.0);
        metrics.record_auth_decision(false, "missing_api_key", "admin:read");
        metrics.record_quota_decision(true, "llm", "free");
        metrics.record_guardrail_decision("blocked");
        metrics.record_semantic_cache_admission(true, "admitted");
        metrics.record_semantic_cache_lookup("native_cpp_cli", "hit");
        metrics.record_rate_limited();
        metrics.record_upstream_error("/api/llm/*", "POST");
        metrics.record_proxy_inflight_delta(1);
        metrics.record_proxy_inflight_delta(-1);

        let body = metrics.render();

        assert!(body.contains("# TYPE tryops_gateway_requests_total counter"));
        assert!(body.contains(
            "tryops_gateway_requests_total{route=\"/api/llm/*\",method=\"POST\",status=\"200\"} 1"
        ));
        assert!(body.contains(
            "tryops_gateway_request_latency_ms_bucket{route=\"/api/llm/*\",method=\"POST\",status=\"200\",le=\"25\"} 1"
        ));
        assert!(body.contains(
            "tryops_gateway_request_latency_ms_count{route=\"/api/llm/*\",method=\"POST\",status=\"200\"} 1"
        ));
        assert!(body.contains(
            "tryops_gateway_quota_decisions_total{allowed=\"true\",workload=\"llm\",plan=\"free\"} 1"
        ));
        assert!(body.contains(
            "tryops_gateway_auth_decisions_total{allowed=\"false\",reason=\"missing_api_key\",required_scope=\"admin:read\"} 1"
        ));
        assert!(body.contains("tryops_gateway_guardrail_decisions_total{status=\"blocked\"} 1"));
        assert!(body.contains(
            "tryops_gateway_semantic_cache_admissions_total{admitted=\"true\",reason=\"admitted\"} 1"
        ));
        assert!(body.contains(
            "tryops_gateway_semantic_cache_lookups_total{source=\"native_cpp_cli\",result=\"hit\"} 1"
        ));
        assert!(body.contains("tryops_gateway_rate_limited_total 1"));
        assert!(body.contains(
            "tryops_gateway_upstream_errors_total{route=\"/api/llm/*\",method=\"POST\"} 1"
        ));
        assert!(body.contains("tryops_gateway_proxy_inflight 0"));
    }

    #[test]
    fn gateway_route_label_bounds_prometheus_cardinality() {
        let llm = "/api/llm/generate?x=1".parse::<Uri>().unwrap();
        let vton = "/api/vton/jobs/job-123".parse::<Uri>().unwrap();
        let model = "/api/models/candidate-1/promote".parse::<Uri>().unwrap();
        let other = "/api/dashboard".parse::<Uri>().unwrap();

        assert_eq!(gateway_route_label(&llm), "/api/llm/*");
        assert_eq!(gateway_route_label(&vton), "/api/vton/*");
        assert_eq!(gateway_route_label(&model), "/api/models/*");
        assert_eq!(gateway_route_label(&other), "/api/*");
    }
}
