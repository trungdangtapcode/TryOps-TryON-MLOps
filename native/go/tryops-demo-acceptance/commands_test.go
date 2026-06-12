package main

import "testing"

func TestTailString(t *testing.T) {
	got := tailString("abcdef", 3)
	if got != "def" {
		t.Fatalf("tailString = %q", got)
	}
}

func TestContainsExitCode(t *testing.T) {
	if !containsExitCode(2, []int{0, 2}) {
		t.Fatal("expected exit code match")
	}
	if containsExitCode(1, []int{0, 2}) {
		t.Fatal("did not expect exit code match")
	}
}

func TestMissingSubstrings(t *testing.T) {
	missing := missingSubstrings(`{"approved": false}`, []string{"approved", "critical"})
	if len(missing) != 1 || missing[0] != "critical" {
		t.Fatalf("unexpected missing list: %#v", missing)
	}
}
