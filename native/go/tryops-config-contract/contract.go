package main

func expectedServices() []serviceContract {
	return []serviceContract{
		{
			Name:          "postgres",
			RequiredEnv:   []string{"POSTGRES_USER", "POSTGRES_PASSWORD_FILE", "POSTGRES_DB"},
			RequiredPorts: []string{"TRYOPS_POSTGRES_PORT"},
			RequireHealth: true,
			RequiredSecrets: []string{
				"tryops_postgres_password",
			},
		},
		{
			Name:          "valkey",
			RequiredPorts: []string{"TRYOPS_VALKEY_PORT"},
			RequireHealth: true,
		},
		{
			Name:          "minio",
			RequiredEnv:   []string{"MINIO_ROOT_USER_FILE", "MINIO_ROOT_PASSWORD_FILE"},
			RequiredPorts: []string{"TRYOPS_MINIO_PORT", "TRYOPS_MINIO_CONSOLE_PORT"},
			RequiredSecrets: []string{
				"tryops_minio_root_user",
				"tryops_minio_root_password",
			},
		},
		{
			Name: "mlflow",
			RequiredEnv: []string{
				"TRYOPS_POSTGRES_USER",
				"TRYOPS_POSTGRES_DB",
				"MLFLOW_S3_ENDPOINT_URL",
			},
			RequiredPorts: []string{"TRYOPS_MLFLOW_PORT"},
			RequiredDepends: map[string]string{
				"postgres": "service_healthy",
				"minio":    "service_started",
			},
			RequiredSecrets: []string{
				"tryops_postgres_password",
				"tryops_minio_root_user",
				"tryops_minio_root_password",
			},
		},
		{
			Name:          "prometheus",
			RequiredPorts: []string{"TRYOPS_PROMETHEUS_PORT"},
			RequiredDepends: map[string]string{
				"otel-collector": "service_started",
				"alertmanager":   "service_started",
			},
		},
		{
			Name:          "alertmanager",
			RequiredPorts: []string{"TRYOPS_ALERTMANAGER_PORT"},
			RequireHealth: true,
		},
		{
			Name:          "grafana",
			RequiredPorts: []string{"TRYOPS_GRAFANA_PORT"},
		},
		{
			Name:          "guardrail",
			RequiredEnv:   []string{"TRYOPS_GUARDRAIL_ADDR"},
			RequiredPorts: []string{"TRYOPS_GUARDRAIL_PORT"},
		},
		{
			Name: "api",
			RequiredEnv: []string{
				"TRYOPS_ENV",
				"MLFLOW_TRACKING_URI",
				"TRYOPS_GUARDRAIL_URL",
			},
			RequiredPorts: []string{"TRYOPS_API_PORT"},
			RequireHealth: true,
			RequiredDepends: map[string]string{
				"mlflow":    "service_started",
				"guardrail": "service_started",
			},
		},
		{
			Name: "gateway",
			RequiredEnv: []string{
				"TRYOPS_GATEWAY_ADDR",
				"TRYOPS_GATEWAY_UPSTREAM",
				"TRYOPS_GATEWAY_GUARDRAIL_URL",
				"TRYOPS_GATEWAY_STATIC_DIR",
				"TRYOPS_GATEWAY_API_KEYS_PATH",
				"TRYOPS_GATEWAY_MAX_BODY_BYTES",
				"TRYOPS_GATEWAY_RATE_LIMIT_PER_MINUTE",
				"TRYOPS_GATEWAY_QUOTA_POSTGRES_DSN_FILE",
				"TRYOPS_GATEWAY_QUOTA_VALKEY_ADDR",
				"TRYOPS_GATEWAY_QUOTA_VALKEY_PREFIX",
				"TRYOPS_GATEWAY_HEALTH_ADDR",
			},
			RequiredPorts: []string{"TRYOPS_GATEWAY_PORT"},
			RequireHealth: true,
			RequiredDepends: map[string]string{
				"postgres":  "service_healthy",
				"valkey":    "service_healthy",
				"guardrail": "service_started",
				"api":       "service_healthy",
			},
			RequiredSecrets: []string{
				"tryops_gateway_quota_postgres_dsn",
			},
		},
	}
}

func expectedSecrets() []secretContract {
	return []secretContract{
		{Name: "tryops_postgres_password", Environment: "TRYOPS_POSTGRES_PASSWORD"},
		{Name: "tryops_minio_root_user", Environment: "TRYOPS_MINIO_ROOT_USER"},
		{Name: "tryops_minio_root_password", Environment: "TRYOPS_MINIO_ROOT_PASSWORD"},
		{Name: "tryops_gateway_quota_postgres_dsn", Environment: "TRYOPS_GATEWAY_QUOTA_POSTGRES_DSN"},
	}
}

func requiredEnvExampleVars() []string {
	return []string{
		"TRYOPS_POSTGRES_USER",
		"TRYOPS_POSTGRES_DB",
		"TRYOPS_POSTGRES_PASSWORD",
		"TRYOPS_MINIO_ROOT_USER",
		"TRYOPS_MINIO_ROOT_PASSWORD",
		"TRYOPS_GATEWAY_QUOTA_POSTGRES_DSN",
		"TRYOPS_WEBHOOK_SECRET",
		"TRYOPS_GITHUB_WEBHOOK_SECRET",
		"ANTHROPIC_API_KEY",
	}
}

func requiredVolumes() []string {
	return []string{
		"alertmanager-data",
		"postgres-data",
		"valkey-data",
		"minio-data",
		"grafana-data",
	}
}

func gatewaySourceEnvVars() []string {
	return []string{
		"TRYOPS_GATEWAY_ADDR",
		"TRYOPS_GATEWAY_UPSTREAM",
		"TRYOPS_GATEWAY_GUARDRAIL_URL",
		"TRYOPS_GATEWAY_STATIC_DIR",
		"TRYOPS_GATEWAY_API_KEYS_PATH",
		"TRYOPS_GATEWAY_MAX_BODY_BYTES",
		"TRYOPS_GATEWAY_RATE_LIMIT_PER_MINUTE",
		"TRYOPS_GATEWAY_QUOTA_POSTGRES_DSN_FILE",
		"TRYOPS_GATEWAY_QUOTA_VALKEY_ADDR",
		"TRYOPS_GATEWAY_QUOTA_VALKEY_PREFIX",
		"TRYOPS_GATEWAY_HEALTH_ADDR",
	}
}
