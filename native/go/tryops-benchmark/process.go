package main

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"time"
)

type ManagedProcess struct {
	Name string
	Cmd  *exec.Cmd
}

func startPythonAPI(ctx context.Context, config BenchmarkConfig) (*ManagedProcess, error) {
	cmd := exec.CommandContext(
		ctx,
		config.PythonBin,
		"-m",
		"uvicorn",
		"tryops.api:create_app",
		"--factory",
		"--host",
		"127.0.0.1",
		"--port",
		fmt.Sprintf("%d", config.PythonPort),
		"--log-level",
		"warning",
	)
	cmd.Env = append(os.Environ(), "PYTHONPATH=src")
	cmd.Stdout = io.Discard
	cmd.Stderr = io.Discard
	if err := cmd.Start(); err != nil {
		return nil, err
	}
	process := &ManagedProcess{Name: "python_fastapi", Cmd: cmd}
	if !waitReady(fmt.Sprintf("http://127.0.0.1:%d/health", config.PythonPort), 15*time.Second) {
		_ = process.Stop()
		return nil, errors.New("python FastAPI did not become ready")
	}
	return process, nil
}

func startGateway(ctx context.Context, config BenchmarkConfig) (*ManagedProcess, error) {
	cmd := exec.CommandContext(ctx, config.GatewayBin)
	cmd.Env = append(
		os.Environ(),
		fmt.Sprintf("TRYOPS_GATEWAY_ADDR=127.0.0.1:%d", config.GatewayPort),
		fmt.Sprintf("TRYOPS_GATEWAY_UPSTREAM=http://127.0.0.1:%d", config.PythonPort),
		"TRYOPS_GATEWAY_RATE_LIMIT_PER_MINUTE=1000000",
	)
	cmd.Stdout = io.Discard
	cmd.Stderr = io.Discard
	if err := cmd.Start(); err != nil {
		return nil, err
	}
	process := &ManagedProcess{Name: "native_rust_gateway", Cmd: cmd}
	if !waitReady(fmt.Sprintf("http://127.0.0.1:%d/health", config.GatewayPort), 15*time.Second) {
		_ = process.Stop()
		return nil, errors.New("Rust gateway did not become ready")
	}
	return process, nil
}

func (p *ManagedProcess) Stop() error {
	if p == nil || p.Cmd == nil || p.Cmd.Process == nil {
		return nil
	}
	if err := p.Cmd.Process.Signal(os.Interrupt); err != nil {
		_ = p.Cmd.Process.Kill()
		return err
	}
	done := make(chan error, 1)
	go func() {
		done <- p.Cmd.Wait()
	}()
	select {
	case <-time.After(3 * time.Second):
		_ = p.Cmd.Process.Kill()
		<-done
	case <-done:
	}
	return nil
}

func waitReady(url string, timeout time.Duration) bool {
	deadline := time.Now().Add(timeout)
	client := &http.Client{Timeout: time.Second}
	for time.Now().Before(deadline) {
		resp, err := client.Get(url)
		if err == nil {
			_, _ = io.Copy(io.Discard, resp.Body)
			_ = resp.Body.Close()
			if resp.StatusCode == http.StatusOK {
				return true
			}
		}
		time.Sleep(200 * time.Millisecond)
	}
	return false
}
