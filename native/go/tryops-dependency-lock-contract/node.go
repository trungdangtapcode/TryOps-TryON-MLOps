package main

import (
	"fmt"
	"sort"
)

type packageJSON struct {
	Name            string            `json:"name"`
	Dependencies    map[string]string `json:"dependencies"`
	DevDependencies map[string]string `json:"devDependencies"`
}

type packageLock struct {
	Name            string                            `json:"name"`
	LockfileVersion int                               `json:"lockfileVersion"`
	Packages        map[string]map[string]interface{} `json:"packages"`
}

func validateNode(cfg Config) (NodeSummary, []Check) {
	checks := []Check{}
	pkg, err := readJSON[packageJSON](cfg.RootPath, cfg.PackageJSONPath)
	checks = append(checks, check("node.package_json.present", err == nil, cfg.PackageJSONPath))

	lock, err := readJSON[packageLock](cfg.RootPath, cfg.PackageLockPath)
	checks = append(checks, check("node.package_lock.present", err == nil, cfg.PackageLockPath))

	direct := []string{}
	if pkg.Dependencies != nil {
		for name := range pkg.Dependencies {
			direct = append(direct, name)
		}
	}
	if pkg.DevDependencies != nil {
		for name := range pkg.DevDependencies {
			direct = append(direct, name)
		}
	}
	sort.Strings(direct)

	integrityCount := 0
	if lock.Packages != nil {
		for path, meta := range lock.Packages {
			if path == "" {
				continue
			}
			if _, ok := meta["integrity"].(string); ok {
				integrityCount++
			}
		}
	}
	checks = append(checks, check("node.package_lock.version3", lock.LockfileVersion == 3, fmt.Sprintf("%d", lock.LockfileVersion)))
	checks = append(checks, check("node.package_lock.root_matches", lock.Name == pkg.Name && pkg.Name != "", lock.Name))
	checks = append(checks, check("node.package_lock.integrity_coverage", integrityCount > len(direct), formatCount(integrityCount)))
	missing := []string{}
	for _, dep := range direct {
		if _, ok := lock.Packages["node_modules/"+dep]; !ok {
			missing = append(missing, dep)
		}
	}
	checks = append(checks, check("node.direct_dependencies_locked", len(missing) == 0 && len(direct) > 0, fmt.Sprintf("missing=%v", missing)))

	return NodeSummary{
		PackageJSONPath:    cfg.PackageJSONPath,
		PackageLockPath:    cfg.PackageLockPath,
		LockfileVersion:    lock.LockfileVersion,
		DirectDependencies: direct,
		LockedPackageCount: len(lock.Packages),
		IntegrityCount:     integrityCount,
	}, checks
}
