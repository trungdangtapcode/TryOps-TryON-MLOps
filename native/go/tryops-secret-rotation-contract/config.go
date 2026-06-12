package main

import "flag"

func parseConfig() Config {
	cfg := Config{}
	flag.StringVar(&cfg.RootPath, "root", ".", "repository root")
	flag.StringVar(&cfg.PolicyPath, "policy", "configs/secret_rotation_policy.json", "secret rotation policy path")
	flag.StringVar(&cfg.ComposePath, "compose", "docker-compose.yml", "Compose file path")
	flag.StringVar(&cfg.EnvExamplePath, "env-example", ".env.example", "env example path")
	flag.StringVar(&cfg.OutputPath, "output", "artifacts/eval/secrets/native_secret_rotation_contract.json", "JSON evidence output path")
	flag.Parse()
	return cfg
}
