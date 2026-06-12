package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

const maxResponseBytes = 4 * 1024 * 1024

func doJSON(ctx context.Context, client *http.Client, method string, url string, payload map[string]interface{}) (httpJSONResponse, error) {
	var body io.Reader
	if payload != nil {
		encoded, err := json.Marshal(payload)
		if err != nil {
			return httpJSONResponse{}, err
		}
		body = bytes.NewReader(encoded)
	}

	request, err := http.NewRequestWithContext(ctx, method, url, body)
	if err != nil {
		return httpJSONResponse{}, err
	}
	request.Header.Set("Accept", "application/json")
	request.Header.Set("X-TryOps-Native-Runner", "go-job-runner")
	if payload != nil {
		request.Header.Set("Content-Type", "application/json")
	}

	response, err := client.Do(request)
	if err != nil {
		return httpJSONResponse{}, err
	}
	defer response.Body.Close()

	responseBody, err := io.ReadAll(io.LimitReader(response.Body, maxResponseBytes))
	if err != nil {
		return httpJSONResponse{StatusCode: response.StatusCode}, err
	}
	data := map[string]interface{}{}
	if len(responseBody) > 0 {
		if err := json.Unmarshal(responseBody, &data); err != nil {
			return httpJSONResponse{StatusCode: response.StatusCode, Body: responseBody}, fmt.Errorf("decode json response: %w", err)
		}
	}
	return httpJSONResponse{StatusCode: response.StatusCode, Body: responseBody, Data: data}, nil
}
