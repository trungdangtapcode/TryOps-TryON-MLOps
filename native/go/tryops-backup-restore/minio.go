package main

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

func minioPlan(cfg Config, checks *[]Check) MinIOSummary {
	summary := MinIOSummary{
		Tool:          "mc mirror",
		Container:     cfg.MinIOContainer,
		SourceBucket:  cfg.MinIOBucket,
		RestoreBucket: cfg.MinIORestoreBucket,
	}
	addCheck(checks, "minio.docker.available", commandAvailable("docker"), "docker on PATH")
	addCheck(checks, "minio.container.configured", cfg.MinIOContainer != "", cfg.MinIOContainer)
	addCheck(checks, "minio.source_bucket.configured", cfg.MinIOBucket != "", cfg.MinIOBucket)
	addCheck(checks, "minio.restore_bucket.isolated", cfg.MinIORestoreBucket != "" && cfg.MinIORestoreBucket != cfg.MinIOBucket, cfg.MinIORestoreBucket)
	return summary
}

func runMinIOLive(ctx context.Context, cfg Config, runID string, checks *[]Check) MinIOSummary {
	summary := minioPlan(cfg, checks)
	addCheck(checks, "minio.credentials.present", true, minioCredentialDetail(cfg))
	if err := os.MkdirAll(cfg.BackupDir, 0o755); err != nil {
		addCheck(checks, "minio.backup_dir.create", false, err.Error())
		return summary
	}
	seedContent := "tryops backup restore drill " + runID + "\n"
	seedPath := filepath.Join(cfg.BackupDir, "minio-seed-"+runID+".txt")
	if err := os.WriteFile(seedPath, []byte(seedContent), 0o644); err != nil {
		addCheck(checks, "minio.seed.write", false, err.Error())
		return summary
	}
	addCheck(checks, "minio.seed.write", true, seedPath)
	containerSeedPath := "/tmp/tryops-minio-seed-" + runID + ".txt"
	if _, _, err := runCommand(ctx, 20*time.Second, "docker", "cp", seedPath, cfg.MinIOContainer+":"+containerSeedPath); err != nil {
		addCheck(checks, "minio.seed.copy_to_container", false, err.Error())
		return summary
	}
	addCheck(checks, "minio.seed.copy_to_container", true, cfg.MinIOContainer)

	objectKey := "backup-drill/" + runID + "/seed.txt"
	restoredKey := runID + "/seed.txt"
	backupPath := "/tmp/tryops-minio-backup-" + runID
	summary.ObjectKey = objectKey
	summary.RestoredKey = restoredKey
	summary.BackupPath = backupPath
	summary.ObjectBytes = int64(len(seedContent))

	script := strings.Join([]string{
		"set -eu",
		minioAliasCommand(cfg),
		"mc mb -p local/" + shellQuote(cfg.MinIOBucket) + " >/dev/null 2>&1 || true",
		"mc mb -p local/" + shellQuote(cfg.MinIORestoreBucket) + " >/dev/null 2>&1 || true",
		"mc cp " + shellQuote(containerSeedPath) + " local/" + shellQuote(cfg.MinIOBucket+"/"+objectKey) + " >/dev/null",
		"rm -rf " + shellQuote(backupPath),
		"mkdir -p " + shellQuote(backupPath),
		"mc mirror --overwrite local/" + shellQuote(cfg.MinIOBucket+"/backup-drill/"+runID) + " " + shellQuote(backupPath) + " >/dev/null",
		"mc mirror --overwrite " + shellQuote(backupPath) + " local/" + shellQuote(cfg.MinIORestoreBucket+"/"+runID) + " >/dev/null",
		"mc stat local/" + shellQuote(cfg.MinIORestoreBucket+"/"+restoredKey) + " >/dev/null",
		"mc cat local/" + shellQuote(cfg.MinIORestoreBucket+"/"+restoredKey),
	}, "\n")
	stdout, _, err := runCommand(ctx, 90*time.Second, "docker", "exec", cfg.MinIOContainer, "sh", "-lc", script)
	if err != nil {
		addCheck(checks, "minio.mirror_restore", false, err.Error())
		cleanupMinIO(ctx, cfg, runID, backupPath, containerSeedPath, checks, &summary)
		return summary
	}
	restored := stdout == seedContent
	summary.RestoredObject = restored
	addCheck(checks, "minio.mirror_restore", restored, fmt.Sprintf("restored=%s bytes=%d", restoredKey, len(stdout)))
	if restored {
		addCheck(checks, "minio.object_bytes_match", int64(len(stdout)) == summary.ObjectBytes, fmt.Sprintf("%d bytes", len(stdout)))
	}
	cleanupMinIO(ctx, cfg, runID, backupPath, containerSeedPath, checks, &summary)
	return summary
}

func cleanupMinIO(ctx context.Context, cfg Config, runID string, backupPath string, containerSeedPath string, checks *[]Check, summary *MinIOSummary) {
	if !cfg.Cleanup {
		addCheck(checks, "minio.restore_cleanup", true, "cleanup disabled; restore objects kept")
		return
	}
	script := strings.Join([]string{
		"set -eu",
		minioAliasCommand(cfg),
		"mc rm --recursive --force local/" + shellQuote(cfg.MinIORestoreBucket+"/"+runID) + " >/dev/null 2>&1 || true",
		"mc rm --recursive --force local/" + shellQuote(cfg.MinIOBucket+"/backup-drill/"+runID) + " >/dev/null 2>&1 || true",
		"rm -rf " + shellQuote(backupPath) + " " + shellQuote(containerSeedPath),
	}, "\n")
	if _, _, err := runCommand(ctx, 30*time.Second, "docker", "exec", cfg.MinIOContainer, "sh", "-lc", script); err != nil {
		addCheck(checks, "minio.restore_cleanup", false, err.Error())
		return
	}
	summary.CleanedUp = true
	addCheck(checks, "minio.restore_cleanup", true, runID)
}

func minioAliasCommand(cfg Config) string {
	access := `"${MINIO_ROOT_USER:?MINIO_ROOT_USER missing}"`
	secret := `"${MINIO_ROOT_PASSWORD:?MINIO_ROOT_PASSWORD missing}"`
	if cfg.MinIOAccessKey != "" {
		access = shellQuote(cfg.MinIOAccessKey)
	}
	if cfg.MinIOSecretKey != "" {
		secret = shellQuote(cfg.MinIOSecretKey)
	}
	return "mc alias set local http://127.0.0.1:9000 " + access + " " + secret + " >/dev/null"
}

func minioCredentialDetail(cfg Config) string {
	if cfg.MinIOAccessKey != "" && cfg.MinIOSecretKey != "" {
		return "credentials configured from CLI/env"
	}
	return "using container MINIO_ROOT_USER/MINIO_ROOT_PASSWORD"
}
