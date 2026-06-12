package main

import "strings"

func contains(value string, expected string) bool {
	return strings.Contains(value, expected)
}

func uniqueSorted(values []string) []string {
	seen := map[string]bool{}
	out := []string{}
	for _, value := range values {
		if value == "" || seen[value] {
			continue
		}
		seen[value] = true
		out = append(out, value)
	}
	for left := 0; left < len(out); left++ {
		for right := left + 1; right < len(out); right++ {
			if out[right] < out[left] {
				out[left], out[right] = out[right], out[left]
			}
		}
	}
	return out
}
