package main

type Config struct {
	Root      string
	Output    string
	AccessKey string
	SecretKey string
	Region    string
}

type DVCRemote struct {
	Name     string `json:"name"`
	URL      string `json:"url"`
	Endpoint string `json:"endpoint"`
	Bucket   string `json:"bucket"`
	Prefix   string `json:"prefix"`
}

type CacheSummary struct {
	Count      int      `json:"count"`
	TotalBytes int64    `json:"total_bytes"`
	Samples    []string `json:"samples"`
}

type LockSummary struct {
	Present        bool     `json:"present"`
	StageNames     []string `json:"stage_names"`
	OutputPaths    []string `json:"output_paths"`
	HasOutputHash  bool     `json:"has_output_hash"`
	HasDependency  bool     `json:"has_dependency"`
	ContainsDVCOut bool     `json:"contains_dvc_output"`
}

type Report struct {
	SchemaVersion string       `json:"schema_version"`
	GeneratedAt   string       `json:"generated_at"`
	Passed        bool         `json:"passed"`
	Root          string       `json:"root"`
	Remote        DVCRemote    `json:"remote"`
	Lock          LockSummary  `json:"lock"`
	LocalCache    CacheSummary `json:"local_cache"`
	RemoteCache   CacheSummary `json:"remote_cache"`
	Checks        []Check      `json:"checks"`
}

type Check struct {
	Name   string `json:"name"`
	Passed bool   `json:"passed"`
	Detail string `json:"detail"`
}
