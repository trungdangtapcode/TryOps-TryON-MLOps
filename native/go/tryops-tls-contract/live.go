package main

import (
	"context"
	"crypto/tls"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"strings"
	"time"
)

func evaluateLive(ctx context.Context, cfg Config, checks *[]Check) LiveSummary {
	summary := LiveSummary{URL: cfg.URL}
	parsed, err := url.Parse(cfg.URL)
	if err != nil {
		addCheck(checks, "live.url.parse", false, err.Error())
		return summary
	}
	addCheck(checks, "live.url.parse", parsed.Scheme == "https", cfg.URL)
	host := parsed.Host
	if !strings.Contains(host, ":") {
		host += ":443"
	}
	dialer := &net.Dialer{Timeout: 2 * time.Second}
	conn, err := tls.DialWithDialer(dialer, "tcp", host, &tls.Config{
		InsecureSkipVerify: true,
		MinVersion:         tls.VersionTLS12,
	})
	if err != nil {
		addCheck(checks, "live.tls.handshake", false, err.Error())
		return summary
	}
	state := conn.ConnectionState()
	_ = conn.Close()
	summary.TLSVersion = tlsVersionName(state.Version)
	summary.CipherSuite = tls.CipherSuiteName(state.CipherSuite)
	summary.PeerCertificates = len(state.PeerCertificates)
	addCheck(checks, "live.tls.handshake", true, summary.TLSVersion+" "+summary.CipherSuite)
	addCheck(checks, "live.tls.min_version", state.Version >= tls.VersionTLS12, summary.TLSVersion)
	addCheck(checks, "live.tls.peer_certificate", len(state.PeerCertificates) > 0, fmt.Sprintf("%d certificates", len(state.PeerCertificates)))

	client := &http.Client{
		Timeout: 3 * time.Second,
		Transport: &http.Transport{
			TLSClientConfig: &tls.Config{InsecureSkipVerify: true, MinVersion: tls.VersionTLS12},
		},
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, cfg.URL, nil)
	if err != nil {
		addCheck(checks, "live.https.request", false, err.Error())
		return summary
	}
	resp, err := client.Do(req)
	if err != nil {
		addCheck(checks, "live.https.request", false, err.Error())
		return summary
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 512))
	summary.HealthStatusCode = resp.StatusCode
	summary.HealthBody = string(body)
	addCheck(checks, "live.https.health", resp.StatusCode == http.StatusOK && strings.Contains(summary.HealthBody, `"status":"ok"`), fmt.Sprintf("status=%d body=%s", resp.StatusCode, summary.HealthBody))

	plainURL := "http://" + parsed.Host + parsed.Path
	plainClient := &http.Client{Timeout: 2 * time.Second}
	plainResp, err := plainClient.Get(plainURL)
	if err != nil {
		summary.PlainHTTPError = err.Error()
		addCheck(checks, "live.plain_http.rejected", true, err.Error())
		return summary
	}
	defer plainResp.Body.Close()
	rejected := plainResp.StatusCode >= 400
	summary.PlainHTTPError = fmt.Sprintf("plain HTTP returned status %d", plainResp.StatusCode)
	addCheck(checks, "live.plain_http.rejected", rejected, summary.PlainHTTPError)
	return summary
}

func tlsVersionName(version uint16) string {
	switch version {
	case tls.VersionTLS13:
		return "TLS1.3"
	case tls.VersionTLS12:
		return "TLS1.2"
	case tls.VersionTLS11:
		return "TLS1.1"
	case tls.VersionTLS10:
		return "TLS1.0"
	default:
		return fmt.Sprintf("0x%x", version)
	}
}
