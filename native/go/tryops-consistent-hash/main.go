package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"sort"
	"strconv"
	"strings"
)

// Report is the JSON emitted on stdout.
type Report struct {
	Nodes           int            `json:"nodes"`
	Replicas        int            `json:"replicas"`
	TotalKeys       int            `json:"total_keys"`
	Distribution    map[string]int `json:"distribution"`
	MaxLoad         int            `json:"max_load"`
	MinLoad         int            `json:"min_load"`
	MeanLoad        float64        `json:"mean_load"`
	ImbalanceRatio  float64        `json:"imbalance_ratio"`  // max/mean
	RemovedNode     string         `json:"removed_node"`
	KeysMoved       int            `json:"keys_moved_on_removal"`
	MovedFraction   float64        `json:"moved_fraction"`
	IdealFraction   float64        `json:"ideal_fraction"` // 1/N
	MinimalDisrupt  bool           `json:"minimal_disruption"`
}

func main() {
	replicas := 150
	var nodes []string
	var keys []string

	scanner := bufio.NewScanner(os.Stdin)
	scanner.Buffer(make([]byte, 0, 64*1024), 4*1024*1024)
	for scanner.Scan() {
		line := scanner.Text()
		if line == "" {
			continue
		}
		k, v, ok := cut(line, "=")
		if !ok {
			keys = append(keys, line)
			continue
		}
		switch k {
		case "replicas":
			if n, err := strconv.Atoi(v); err == nil {
				replicas = n
			}
		case "node":
			nodes = append(nodes, v)
		case "key":
			keys = append(keys, v)
		default:
			keys = append(keys, line)
		}
	}

	ring := NewHashRing(replicas)
	for _, n := range nodes {
		ring.Add(n)
	}

	dist := make(map[string]int)
	for _, n := range nodes {
		dist[n] = 0
	}
	assign := make(map[string]string, len(keys))
	for _, key := range keys {
		owner := ring.Get(key)
		assign[key] = owner
		dist[owner]++
	}

	report := Report{
		Nodes:        ring.NodeCount(),
		Replicas:     replicas,
		TotalKeys:    len(keys),
		Distribution: dist,
	}

	// load balance stats
	report.MaxLoad = math.MinInt32
	report.MinLoad = math.MaxInt32
	for _, c := range dist {
		if c > report.MaxLoad {
			report.MaxLoad = c
		}
		if c < report.MinLoad {
			report.MinLoad = c
		}
	}
	if len(dist) > 0 {
		report.MeanLoad = float64(len(keys)) / float64(len(dist))
		if report.MeanLoad > 0 {
			report.ImbalanceRatio = float64(report.MaxLoad) / report.MeanLoad
		}
	}

	// minimal-disruption check: remove one node, count keys that change owner.
	if len(nodes) > 1 && len(keys) > 0 {
		removed := nodes[0]
		report.RemovedNode = removed
		ring.Remove(removed)
		moved := 0
		for _, key := range keys {
			if ring.Get(key) != assign[key] {
				moved++
			}
		}
		report.KeysMoved = moved
		report.MovedFraction = float64(moved) / float64(len(keys))
		report.IdealFraction = 1.0 / float64(len(nodes))
		// a correct ring moves only ~the removed node's share (allow 2x slack).
		report.MinimalDisrupt = report.MovedFraction <= 2.0*report.IdealFraction
	} else {
		report.MinimalDisrupt = true
	}

	encoded, _ := json.Marshal(report)
	fmt.Println(string(encoded))
	if !report.MinimalDisrupt {
		os.Exit(2)
	}
}

func cut(s, sep string) (string, string, bool) {
	if i := strings.Index(s, sep); i >= 0 {
		return s[:i], s[i+len(sep):], true
	}
	return s, "", false
}

// ensure deterministic node ordering when iterating (used by tests via helper).
func sortedKeys(m map[string]int) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}
