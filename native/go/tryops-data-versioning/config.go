package main

import (
	"flag"
	"os"
)

func parseConfig() Config {
	var cfg Config
	flag.StringVar(&cfg.Root, "root", ".", "repository root")
	flag.StringVar(&cfg.Output, "output", "artifacts/eval/data_versioning/dvc_minio_report.json", "report output path")
	flag.StringVar(&cfg.AccessKey, "access-key", getenvDefault("AWS_ACCESS_KEY_ID", "tryops"), "S3 access key")
	flag.StringVar(&cfg.SecretKey, "secret-key", getenvDefault("AWS_SECRET_ACCESS_KEY", "tryops123"), "S3 secret key")
	flag.StringVar(&cfg.Region, "region", getenvDefault("AWS_REGION", "us-east-1"), "S3 signing region")
	flag.Parse()
	return cfg
}

func getenvDefault(key string, fallback string) string {
	value := os.Getenv(key)
	if value == "" {
		return fallback
	}
	return value
}
