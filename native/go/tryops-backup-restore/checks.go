package main

func addCheck(checks *[]Check, name string, passed bool, detail string) {
	*checks = append(*checks, Check{Name: name, Passed: passed, Detail: detail})
}

func countPassed(checks []Check) int {
	passed := 0
	for _, check := range checks {
		if check.Passed {
			passed++
		}
	}
	return passed
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
