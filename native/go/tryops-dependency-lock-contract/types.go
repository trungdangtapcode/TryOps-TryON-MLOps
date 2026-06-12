package main

const schemaVersion = "tryops.native_dependency_lock_contract.v1"

type Config struct {
	RootPath        string
	PyprojectPath   string
	UVLockPath      string
	PackageJSONPath string
	PackageLockPath string
	CargoTomlPath   string
	CargoLockPath   string
	GoRootPath      string
	MakefilePath    string
	OutputPath      string
}

type Check struct {
	Name   string `json:"name"`
	Passed bool   `json:"passed"`
	Detail string `json:"detail"`
}

type EvidenceRef struct {
	Name          string `json:"name"`
	Path          string `json:"path"`
	SchemaVersion string `json:"schema_version,omitempty"`
	Status        string `json:"status"`
	Detail        string `json:"detail,omitempty"`
}

type ResearchRef struct {
	Name string `json:"name"`
	URL  string `json:"url"`
	Use  string `json:"use"`
}

type PythonPackage struct {
	Name    string `json:"name"`
	Version string `json:"version"`
}

type PythonSummary struct {
	PyprojectPath       string          `json:"pyproject_path"`
	LockPath            string          `json:"lock_path"`
	DeclaredCount       int             `json:"declared_count"`
	LockedPackageCount  int             `json:"locked_package_count"`
	HashCount           int             `json:"hash_count"`
	CriticalPackages    []PythonPackage `json:"critical_packages"`
	MissingDeclarations []string        `json:"missing_declarations,omitempty"`
}

type NodeSummary struct {
	PackageJSONPath    string   `json:"package_json_path"`
	PackageLockPath    string   `json:"package_lock_path"`
	LockfileVersion    int      `json:"lockfile_version"`
	DirectDependencies []string `json:"direct_dependencies"`
	LockedPackageCount int      `json:"locked_package_count"`
	IntegrityCount     int      `json:"integrity_count"`
}

type RustSummary struct {
	CargoTomlPath      string   `json:"cargo_toml_path"`
	CargoLockPath      string   `json:"cargo_lock_path"`
	DirectDependencies []string `json:"direct_dependencies"`
	LockedPackageCount int      `json:"locked_package_count"`
	ChecksumCount      int      `json:"checksum_count"`
}

type GoModuleSummary struct {
	Path             string   `json:"path"`
	Module           string   `json:"module"`
	Requires         []string `json:"requires"`
	HasGoSum         bool     `json:"has_go_sum"`
	ChecksumCoverage bool     `json:"checksum_coverage"`
}

type Summary struct {
	PassedChecks       int `json:"passed_checks"`
	FailedChecks       int `json:"failed_checks"`
	TotalChecks        int `json:"total_checks"`
	PythonLocked       int `json:"python_locked"`
	NodeLocked         int `json:"node_locked"`
	RustLocked         int `json:"rust_locked"`
	GoModules          int `json:"go_modules"`
	GoExternalModules  int `json:"go_external_modules"`
	GoChecksumCoverage int `json:"go_checksum_coverage"`
}

type Report struct {
	SchemaVersion   string            `json:"schema_version"`
	GeneratedAt     string            `json:"generated_at"`
	Passed          bool              `json:"passed"`
	ProductionReady bool              `json:"production_ready"`
	CoverageLevel   string            `json:"coverage_level"`
	Python          PythonSummary     `json:"python"`
	Node            NodeSummary       `json:"node"`
	Rust            RustSummary       `json:"rust"`
	GoModules       []GoModuleSummary `json:"go_modules"`
	Checks          []Check           `json:"checks"`
	Evidence        []EvidenceRef     `json:"evidence"`
	Research        []ResearchRef     `json:"research"`
	Notes           []string          `json:"notes"`
	Summary         Summary           `json:"summary"`
}
