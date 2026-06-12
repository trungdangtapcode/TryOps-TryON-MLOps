package main

import (
	"fmt"
	"testing"
)

// Mapping is deterministic and every key resolves to a real node.
func TestDeterministicAndTotal(t *testing.T) {
	r := NewHashRing(100)
	for _, n := range []string{"a", "b", "c"} {
		r.Add(n)
	}
	for i := 0; i < 1000; i++ {
		k := fmt.Sprintf("key-%d", i)
		got := r.Get(k)
		if got == "" {
			t.Fatalf("key %s mapped to empty node", k)
		}
		if got != r.Get(k) {
			t.Fatalf("non-deterministic mapping for %s", k)
		}
	}
}

// Virtual nodes keep the load reasonably balanced.
func TestBalancedDistribution(t *testing.T) {
	r := NewHashRing(200)
	nodes := []string{"n0", "n1", "n2", "n3", "n4"}
	for _, n := range nodes {
		r.Add(n)
	}
	const total = 50000
	dist := map[string]int{}
	for i := 0; i < total; i++ {
		dist[r.Get(fmt.Sprintf("req-%d", i))]++
	}
	mean := float64(total) / float64(len(nodes))
	for n, c := range dist {
		ratio := float64(c) / mean
		if ratio < 0.7 || ratio > 1.3 {
			t.Fatalf("node %s load %d off balance (ratio %.2f)", n, c, ratio)
		}
	}
}

// Removing a node only remaps that node's share of keys (minimal disruption).
func TestMinimalDisruptionOnRemoval(t *testing.T) {
	r := NewHashRing(200)
	nodes := []string{"a", "b", "c", "d"}
	for _, n := range nodes {
		r.Add(n)
	}
	const total = 20000
	before := make(map[string]string, total)
	for i := 0; i < total; i++ {
		k := fmt.Sprintf("k-%d", i)
		before[k] = r.Get(k)
	}
	r.Remove("a")
	moved := 0
	for k, prev := range before {
		if r.Get(k) != prev {
			moved++
		}
	}
	frac := float64(moved) / float64(total)
	// ideal is 1/4 = 0.25; allow up to 2x.
	if frac > 0.5 {
		t.Fatalf("too many keys moved on removal: %.3f", frac)
	}
	// keys that did NOT belong to "a" must not move.
	for k, prev := range before {
		if prev != "a" && r.Get(k) != prev {
			t.Fatalf("key %s moved from %s though its node stayed", k, prev)
		}
	}
}

func TestAddIsAlsoMinimal(t *testing.T) {
	r := NewHashRing(200)
	for _, n := range []string{"a", "b", "c"} {
		r.Add(n)
	}
	const total = 20000
	before := make(map[string]string, total)
	for i := 0; i < total; i++ {
		k := fmt.Sprintf("k-%d", i)
		before[k] = r.Get(k)
	}
	r.Add("d")
	moved := 0
	for k, prev := range before {
		if r.Get(k) != prev {
			moved++
		}
	}
	frac := float64(moved) / float64(total)
	// adding a 4th node should pull ~1/4 of keys; allow up to 2x.
	if frac > 0.5 {
		t.Fatalf("too many keys moved on add: %.3f", frac)
	}
}

func TestSortedKeysHelper(t *testing.T) {
	got := sortedKeys(map[string]int{"b": 1, "a": 2, "c": 3})
	if got[0] != "a" || got[2] != "c" {
		t.Fatalf("sortedKeys not sorted: %v", got)
	}
}
