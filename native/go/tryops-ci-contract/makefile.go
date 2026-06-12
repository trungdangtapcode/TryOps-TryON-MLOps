package main

func validateMakefile(makefile string) []Check {
	checks := []Check{}
	addContains := func(name string, patterns []string) {
		passed, detail := containsAll(makefile, patterns)
		checks = append(checks, Check{Name: name, Passed: passed, Detail: detail})
	}
	addContains("make_ci_target_exists", []string{"ci:", "test", "web-typecheck", "native-go-test", "native-rust-test", "native-cpp-test"})
	addContains("make_ci_supply_chain_evidence", []string{"supply-chain-sample", "vulnerability-scan-sample", "native-container-contract-sample", "native-ci-contract-sample", "evaluation-index-sample"})
	addContains("make_native_ci_contract_targets", []string{"native-ci-contract-build:", "native-ci-contract-test:", "native-ci-contract-sample:"})
	return checks
}
