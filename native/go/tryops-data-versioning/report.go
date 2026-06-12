package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

func buildReport(cfg Config) (Report, error) {
	remote, remoteErr := loadDVCRemote(cfg.Root)
	lock, lockErr := summarizeDVCLock(cfg.Root)
	localCache, localErr := summarizeLocalCache(cfg.Root)

	var remoteCache CacheSummary
	var listErr error
	if remoteErr == nil {
		remoteCache, listErr = summarizeRemoteCache(remote, cfg.AccessKey, cfg.SecretKey, cfg.Region)
	}

	checks := []Check{
		checkFromErr("dvc_config_remote", remoteErr, remote.URL),
		checkFromErr("dvc_lock_read", lockErr, "dvc.lock parsed"),
		checkBool("dvc_lock_present", lock.Present, "dvc.lock exists"),
		checkBool("dvc_lock_has_stage", len(lock.StageNames) > 0, fmt.Sprintf("stages=%v", lock.StageNames)),
		checkBool("dvc_lock_has_output_hash", lock.HasOutputHash && lock.ContainsDVCOut, fmt.Sprintf("outputs=%v", lock.OutputPaths)),
		checkFromErr("local_dvc_cache_walk", localErr, bytesDetail(localCache.Count, localCache.TotalBytes)),
		checkBool("local_dvc_cache_nonempty", localCache.Count > 0, bytesDetail(localCache.Count, localCache.TotalBytes)),
		checkFromErr("minio_list_objects", listErr, remote.Endpoint),
		checkBool("remote_dvc_cache_nonempty", remoteCache.Count > 0, bytesDetail(remoteCache.Count, remoteCache.TotalBytes)),
		checkBool("remote_matches_or_exceeds_local_cache", remoteCache.Count >= localCache.Count && localCache.Count > 0, fmt.Sprintf("local=%d remote=%d", localCache.Count, remoteCache.Count)),
	}
	passed := true
	for _, check := range checks {
		if !check.Passed {
			passed = false
			break
		}
	}
	return Report{
		SchemaVersion: "tryops.dvc_minio_versioning.v1",
		GeneratedAt:   time.Now().UTC().Format(time.RFC3339),
		Passed:        passed,
		Root:          cfg.Root,
		Remote:        remote,
		Lock:          lock,
		LocalCache:    localCache,
		RemoteCache:   remoteCache,
		Checks:        checks,
	}, nil
}

func writeReport(path string, report Report) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	body, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	body = append(body, '\n')
	return os.WriteFile(path, body, 0o644)
}

func checkFromErr(name string, err error, detail string) Check {
	if err != nil {
		return Check{Name: name, Passed: false, Detail: err.Error()}
	}
	return Check{Name: name, Passed: true, Detail: detail}
}

func checkBool(name string, passed bool, detail string) Check {
	return Check{Name: name, Passed: passed, Detail: detail}
}
