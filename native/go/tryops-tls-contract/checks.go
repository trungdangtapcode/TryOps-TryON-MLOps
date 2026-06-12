package main

func addCheck(checks *[]Check, name string, passed bool, detail string) {
	*checks = append(*checks, Check{Name: name, Passed: passed, Detail: detail})
}

func countPassed(checks []Check) int {
	count := 0
	for _, check := range checks {
		if check.Passed {
			count++
		}
	}
	return count
}

func allPassed(checks []Check) bool {
	if len(checks) == 0 {
		return false
	}
	for _, check := range checks {
		if !check.Passed {
			return false
		}
	}
	return true
}
