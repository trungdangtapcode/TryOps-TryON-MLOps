package main

import (
	"context"
	"time"
)

func evaluate(ctx context.Context, cfg Config) Report {
	var checks []Check
	compose := evaluateCompose(cfg.ComposePath, &checks)
	cert := evaluateCertificate(cfg, &checks)
	live := LiveSummary{}
	liveMode := cfg.Mode == "live"
	if liveMode {
		live = evaluateLive(ctx, cfg, &checks)
	}
	coverage := "native_tls_termination_contract"
	if liveMode {
		coverage = "native_tls_termination_live_handshake"
	}
	report := Report{
		SchemaVersion: "tryops.native_tls_contract.v1",
		GeneratedAt:   time.Now().UTC().Format(time.RFC3339),
		Passed:        allPassed(checks),
		CoverageLevel: coverage,
		Mode:          cfg.Mode,
		Summary: Summary{
			PassedChecks:      countPassed(checks),
			TotalChecks:       len(checks),
			LiveHandshake:     liveMode && live.TLSVersion != "",
			ComposeTLSProfile: true,
			CertDaysRemaining: cert.DaysRemaining,
			HTTPSHealth:       liveMode && live.HealthStatusCode == 200,
			PlainHTTPRejected: liveMode && live.PlainHTTPError != "" && !isPlainHTTPSuccess(live),
		},
		Compose:     compose,
		Certificate: cert,
		Live:        live,
		Checks:      checks,
		Research: []ResearchSource{
			{Name: "axum-server TLS rustls", URL: "https://docs.rs/axum-server/0.8.0/axum_server/tls_rustls/index.html", Use: "native Rust HTTPS listener for the gateway"},
			{Name: "rustls ServerConfig", URL: "https://docs.rs/rustls/latest/rustls/server/struct.ServerConfig.html", Use: "TLS server configuration and protocol support"},
			{Name: "Docker Compose secrets", URL: "https://docs.docker.com/compose/how-tos/use-secrets/", Use: "production certificate and private key injection"},
			{Name: "OpenSSL req", URL: "https://docs.openssl.org/master/man1/openssl-req/", Use: "local self-signed certificate generation for smoke evidence"},
		},
		Notes: []string{
			"Plan mode validates the optional Compose TLS profile, secret mounts, rustls env wiring, and local certificate pair.",
			"Live mode starts the Rust gateway with TRYOPS_GATEWAY_TLS_CERT_PATH and TRYOPS_GATEWAY_TLS_KEY_PATH, verifies a TLS handshake, HTTPS health response, and plaintext HTTP rejection.",
		},
	}
	return report
}

func isPlainHTTPSuccess(live LiveSummary) bool {
	return live.PlainHTTPError == "plain HTTP returned status 200"
}
