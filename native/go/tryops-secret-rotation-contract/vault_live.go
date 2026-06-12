package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path"
	"sort"
	"strings"
	"time"
)

type vaultHealthResponse struct {
	Initialized bool   `json:"initialized"`
	Sealed      bool   `json:"sealed"`
	Standby     bool   `json:"standby"`
	Version     string `json:"version"`
}

type vaultReadResponse struct {
	Data struct {
		Data     map[string]interface{} `json:"data"`
		Metadata struct {
			Version int `json:"version"`
		} `json:"metadata"`
	} `json:"data"`
}

type vaultMountsResponse struct {
	Data map[string]interface{} `json:"data"`
}

func exerciseLiveVault(cfg Config, policy Policy, secrets []SecretSummary) ([]Check, LiveReadiness) {
	live := liveReadiness(cfg)
	checks := []Check{
		check("vault.live.requested", cfg.LiveVault, "live Vault exercise requested"),
		check("vault.live.addr_configured", live.VaultAddrConfigured, cfg.VaultAddr),
		check("vault.live.token_path_configured", live.TokenPathConfigured, cfg.WorkloadTokenPath),
		check("vault.live.token_path_readable", live.TokenPathReadable, live.TokenSHA256Prefix),
	}

	authToken, authSource, err := vaultAuthToken(cfg)
	live.AuthSource = authSource
	checks = append(checks, check("vault.live.auth_token_available", err == nil && authToken != "", authSource))
	if err != nil {
		live.Error = err.Error()
		live.Mode = "live_vault_failed"
		return checks, live
	}
	if cfg.VaultAddr == "" {
		live.Error = "VAULT_ADDR is required for --live-vault"
		live.Mode = "live_vault_failed"
		return checks, live
	}

	timeout := time.Duration(cfg.LiveTimeoutSeconds) * time.Second
	if timeout <= 0 {
		timeout = 20 * time.Second
	}
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	client := &http.Client{Timeout: 5 * time.Second}
	health, err := waitVaultHealth(ctx, client, cfg.VaultAddr)
	live.VaultHealthOK = err == nil && health.Initialized && !health.Sealed
	live.VaultInitialized = health.Initialized
	live.VaultSealed = health.Sealed
	live.VaultVersion = health.Version
	checks = append(checks, check("vault.live.health_unsealed", live.VaultHealthOK, fmt.Sprintf("initialized=%t sealed=%t version=%s", health.Initialized, health.Sealed, health.Version)))
	if err != nil {
		live.Error = err.Error()
		live.Mode = "live_vault_failed"
		return checks, live
	}

	mount := strings.Trim(policy.Provider.KVMount, "/")
	if mount == "" {
		mount = "kv"
	}
	live.KVMount = mount
	if err := ensureKVMount(ctx, client, cfg.VaultAddr, authToken, mount); err != nil {
		checks = append(checks, check("vault.live.kv_mount_ready", false, err.Error()))
		live.Error = err.Error()
		live.Mode = "live_vault_failed"
		return checks, live
	}
	checks = append(checks, check("vault.live.kv_mount_ready", true, mount))

	groups := liveSecretGroups(policy, secrets, cfg.LiveSecretPrefix)
	minVersion := 0
	maxVersion := 0
	rotatedProperties := 0
	exercisedPaths := 0
	for _, group := range groups {
		first := generatedSecretValues(group.Properties)
		if err := vaultWrite(ctx, client, cfg.VaultAddr, authToken, group.VaultPath, first); err != nil {
			checks = append(checks, check("vault.live.path."+group.Name+".initial_write", false, err.Error()))
			continue
		}
		firstRead, firstVersion, err := vaultRead(ctx, client, cfg.VaultAddr, authToken, group.VaultPath)
		if err != nil {
			checks = append(checks, check("vault.live.path."+group.Name+".initial_read", false, err.Error()))
			continue
		}
		second := generatedSecretValues(group.Properties)
		if err := vaultWrite(ctx, client, cfg.VaultAddr, authToken, group.VaultPath, second); err != nil {
			checks = append(checks, check("vault.live.path."+group.Name+".rotation_write", false, err.Error()))
			continue
		}
		secondRead, secondVersion, err := vaultRead(ctx, client, cfg.VaultAddr, authToken, group.VaultPath)
		if err != nil {
			checks = append(checks, check("vault.live.path."+group.Name+".rotation_read", false, err.Error()))
			continue
		}
		pathOK := firstVersion >= 1 && secondVersion > firstVersion
		for _, property := range group.Properties {
			before := fmt.Sprint(firstRead[property])
			after := fmt.Sprint(secondRead[property])
			pathOK = pathOK && before == first[property] && after == second[property] && before != after
		}
		if pathOK {
			exercisedPaths++
			rotatedProperties += len(group.Properties)
			minVersion = minNonZero(minVersion, firstVersion)
			minVersion = minNonZero(minVersion, secondVersion)
			if firstVersion > maxVersion {
				maxVersion = firstVersion
			}
			if secondVersion > maxVersion {
				maxVersion = secondVersion
			}
		}
		checks = append(checks, check("vault.live.path."+group.Name+".rotated", pathOK, fmt.Sprintf("properties=%d version=%d->%d", len(group.Properties), firstVersion, secondVersion)))
	}
	live.KVPathsExercised = exercisedPaths
	live.SecretPropertiesRotated = rotatedProperties
	live.MinVersionObserved = minVersion
	live.MaxVersionObserved = maxVersion
	checks = append(checks,
		check("vault.live.all_paths_exercised", exercisedPaths == len(groups), fmt.Sprintf("%d/%d", exercisedPaths, len(groups))),
		check("vault.live.all_secret_properties_rotated", rotatedProperties == len(secrets), fmt.Sprintf("%d/%d", rotatedProperties, len(secrets))),
		check("vault.live.versioning_observed", minVersion >= 1 && maxVersion >= 2, fmt.Sprintf("%d..%d", minVersion, maxVersion)),
	)
	live.LiveExercisePassed = allChecksPassed(checks)
	if live.LiveExercisePassed {
		live.Mode = "live_vault_kv_rotation_passed"
	} else {
		live.Mode = "live_vault_failed"
		live.Error = "one or more live Vault checks failed"
	}
	return checks, live
}

type liveSecretGroup struct {
	Name       string
	VaultPath  string
	Properties []string
}

func liveSecretGroups(policy Policy, secrets []SecretSummary, prefix string) []liveSecretGroup {
	groups := map[string]map[string]bool{}
	mount := strings.Trim(policy.Provider.KVMount, "/")
	if mount == "" {
		mount = "kv"
	}
	for _, secret := range secrets {
		logical := strings.TrimPrefix(secret.VaultPath, mount+"/data/")
		logical = strings.TrimPrefix(logical, "tryops/")
		groupPath := path.Join(mount, "data", strings.Trim(prefix, "/"), logical)
		if groups[groupPath] == nil {
			groups[groupPath] = map[string]bool{}
		}
		groups[groupPath][secret.VaultProperty] = true
	}
	paths := make([]string, 0, len(groups))
	for groupPath := range groups {
		paths = append(paths, groupPath)
	}
	sort.Strings(paths)
	out := make([]liveSecretGroup, 0, len(paths))
	for _, groupPath := range paths {
		properties := make([]string, 0, len(groups[groupPath]))
		for property := range groups[groupPath] {
			properties = append(properties, property)
		}
		sort.Strings(properties)
		out = append(out, liveSecretGroup{Name: sanitizeCheckName(strings.TrimPrefix(groupPath, mount+"/data/")), VaultPath: groupPath, Properties: properties})
	}
	return out
}

func vaultAuthToken(cfg Config) (string, string, error) {
	if cfg.WorkloadTokenPath != "" {
		body, err := readTokenPath(cfg)
		if err != nil {
			return "", "workload_identity_token_path", err
		}
		token := strings.TrimSpace(string(body))
		if token != "" {
			return token, "workload_identity_token_path", nil
		}
	}
	if strings.TrimSpace(cfg.VaultToken) != "" {
		return strings.TrimSpace(cfg.VaultToken), "VAULT_TOKEN", nil
	}
	return "", "", errors.New("VAULT_TOKEN or TRYOPS_WORKLOAD_IDENTITY_TOKEN_PATH is required")
}

func readTokenPath(cfg Config) ([]byte, error) {
	if cfg.WorkloadTokenPath == "" {
		return nil, errors.New("token path is empty")
	}
	return os.ReadFile(joinRoot(cfg.RootPath, cfg.WorkloadTokenPath))
}

func waitVaultHealth(ctx context.Context, client *http.Client, addr string) (vaultHealthResponse, error) {
	var lastErr error
	for {
		health, err := vaultHealth(ctx, client, addr)
		if err == nil && health.Initialized && !health.Sealed {
			return health, nil
		}
		if err != nil {
			lastErr = err
		} else {
			lastErr = fmt.Errorf("vault not ready: initialized=%t sealed=%t", health.Initialized, health.Sealed)
		}
		select {
		case <-ctx.Done():
			return health, lastErr
		case <-time.After(250 * time.Millisecond):
		}
	}
}

func vaultHealth(ctx context.Context, client *http.Client, addr string) (vaultHealthResponse, error) {
	var health vaultHealthResponse
	status, body, err := vaultRequest(ctx, client, http.MethodGet, addr, "", "sys/health", nil)
	if err != nil {
		return health, err
	}
	if status < 200 || status >= 500 {
		return health, fmt.Errorf("vault health status %d: %s", status, string(body))
	}
	if err := json.Unmarshal(body, &health); err != nil {
		return health, err
	}
	return health, nil
}

func ensureKVMount(ctx context.Context, client *http.Client, addr string, token string, mount string) error {
	status, body, err := vaultRequest(ctx, client, http.MethodGet, addr, token, "sys/mounts", nil)
	if err != nil {
		return err
	}
	if status < 200 || status >= 300 {
		return fmt.Errorf("list mounts status %d: %s", status, string(body))
	}
	var mounts vaultMountsResponse
	if err := json.Unmarshal(body, &mounts); err != nil {
		return err
	}
	if _, ok := mounts.Data[mount+"/"]; ok {
		return nil
	}
	payload := map[string]interface{}{
		"type": "kv",
		"options": map[string]string{
			"version": "2",
		},
	}
	status, body, err = vaultRequest(ctx, client, http.MethodPost, addr, token, "sys/mounts/"+mount, payload)
	if err != nil {
		return err
	}
	if status == http.StatusNoContent || (status >= 200 && status < 300) {
		return nil
	}
	if status == http.StatusBadRequest && strings.Contains(string(body), "path is already in use") {
		return nil
	}
	return fmt.Errorf("enable kv mount status %d: %s", status, string(body))
}

func vaultWrite(ctx context.Context, client *http.Client, addr string, token string, vaultPath string, values map[string]string) error {
	payload := map[string]interface{}{"data": values}
	status, body, err := vaultRequest(ctx, client, http.MethodPost, addr, token, vaultPath, payload)
	if err != nil {
		return err
	}
	if status < 200 || status >= 300 {
		return fmt.Errorf("write %s status %d: %s", vaultPath, status, string(body))
	}
	return nil
}

func vaultRead(ctx context.Context, client *http.Client, addr string, token string, vaultPath string) (map[string]interface{}, int, error) {
	status, body, err := vaultRequest(ctx, client, http.MethodGet, addr, token, vaultPath, nil)
	if err != nil {
		return nil, 0, err
	}
	if status < 200 || status >= 300 {
		return nil, 0, fmt.Errorf("read %s status %d: %s", vaultPath, status, string(body))
	}
	var response vaultReadResponse
	if err := json.Unmarshal(body, &response); err != nil {
		return nil, 0, err
	}
	return response.Data.Data, response.Data.Metadata.Version, nil
}

func vaultRequest(ctx context.Context, client *http.Client, method string, addr string, token string, apiPath string, payload interface{}) (int, []byte, error) {
	base, err := url.Parse(strings.TrimRight(addr, "/"))
	if err != nil {
		return 0, nil, err
	}
	base.Path = path.Join(base.Path, "v1", apiPath)
	var body io.Reader
	if payload != nil {
		encoded, err := json.Marshal(payload)
		if err != nil {
			return 0, nil, err
		}
		body = bytes.NewReader(encoded)
	}
	req, err := http.NewRequestWithContext(ctx, method, base.String(), body)
	if err != nil {
		return 0, nil, err
	}
	if token != "" {
		req.Header.Set("X-Vault-Token", token)
	}
	if payload != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := client.Do(req)
	if err != nil {
		return 0, nil, err
	}
	defer resp.Body.Close()
	responseBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return resp.StatusCode, nil, err
	}
	return resp.StatusCode, responseBody, nil
}

func generatedSecretValues(properties []string) map[string]string {
	values := make(map[string]string, len(properties))
	for _, property := range properties {
		values[property] = "tryops-live-" + randomHex(16)
	}
	return values
}

func randomHex(n int) string {
	body := make([]byte, n)
	if _, err := rand.Read(body); err != nil {
		return fmt.Sprintf("%d", time.Now().UnixNano())
	}
	return hex.EncodeToString(body)
}

func sha256Prefix(body []byte) string {
	sum := sha256.Sum256(bytes.TrimSpace(body))
	return hex.EncodeToString(sum[:])[:16]
}

func minNonZero(a int, b int) int {
	if a == 0 {
		return b
	}
	if b == 0 || a < b {
		return a
	}
	return b
}

func allChecksPassed(checks []Check) bool {
	for _, check := range checks {
		if !check.Passed {
			return false
		}
	}
	return true
}

func sanitizeCheckName(value string) string {
	value = strings.Trim(value, "/")
	replacer := strings.NewReplacer("/", "_", ".", "_", "-", "_")
	value = replacer.Replace(value)
	if value == "" {
		return "root"
	}
	return value
}
