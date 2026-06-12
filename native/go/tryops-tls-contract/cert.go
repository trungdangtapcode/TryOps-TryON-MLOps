package main

import (
	"crypto/tls"
	"crypto/x509"
	"encoding/pem"
	"fmt"
	"net"
	"os"
	"time"
)

func evaluateCertificate(cfg Config, checks *[]Check) CertificateSummary {
	summary := CertificateSummary{
		Path:    cfg.CertPath,
		KeyPath: cfg.KeyPath,
	}
	certPEM, err := os.ReadFile(cfg.CertPath)
	if err != nil {
		addCheck(checks, "tls.cert.read", false, err.Error())
		return summary
	}
	addCheck(checks, "tls.cert.read", true, cfg.CertPath)
	block, _ := pem.Decode(certPEM)
	if block == nil {
		addCheck(checks, "tls.cert.pem", false, "no PEM block")
		return summary
	}
	addCheck(checks, "tls.cert.pem", block.Type == "CERTIFICATE", block.Type)
	cert, err := x509.ParseCertificate(block.Bytes)
	if err != nil {
		addCheck(checks, "tls.cert.parse", false, err.Error())
		return summary
	}
	addCheck(checks, "tls.cert.parse", true, cert.Subject.String())
	now := time.Now()
	daysRemaining := int(time.Until(cert.NotAfter).Hours() / 24)
	summary.Subject = cert.Subject.String()
	summary.DNSNames = append([]string{}, cert.DNSNames...)
	for _, ip := range cert.IPAddresses {
		summary.IPAddresses = append(summary.IPAddresses, ip.String())
	}
	summary.NotBefore = cert.NotBefore.UTC().Format(time.RFC3339)
	summary.NotAfter = cert.NotAfter.UTC().Format(time.RFC3339)
	summary.DaysRemaining = daysRemaining
	addCheck(checks, "tls.cert.not_before", !now.Before(cert.NotBefore), summary.NotBefore)
	addCheck(checks, "tls.cert.not_expired", now.Before(cert.NotAfter), summary.NotAfter)
	addCheck(checks, "tls.cert.localhost_san", hasLocalSAN(cert), fmt.Sprintf("dns=%v ip=%v", cert.DNSNames, cert.IPAddresses))
	_, err = tls.LoadX509KeyPair(cfg.CertPath, cfg.KeyPath)
	summary.KeyPairLoads = err == nil
	addCheck(checks, "tls.key_pair.loads", err == nil, keyPairDetail(err))
	return summary
}

func hasLocalSAN(cert *x509.Certificate) bool {
	for _, name := range cert.DNSNames {
		if name == "localhost" || name == "tryops.local" {
			return true
		}
	}
	for _, ip := range cert.IPAddresses {
		if ip.Equal(net.ParseIP("127.0.0.1")) {
			return true
		}
	}
	return false
}

func keyPairDetail(err error) string {
	if err == nil {
		return "certificate and private key match"
	}
	return err.Error()
}
