// Package main implements a consistent-hash ring for routing requests to a set
// of backend nodes (e.g. GPU replicas / shards) at the platform boundary in Go.
//
// Consistent hashing keeps key->node assignments stable when nodes are added or
// removed: only ~1/N of keys move, instead of a full reshuffle as with naive
// modulo hashing. Virtual nodes (replicas) smooth the load distribution.
package main

import (
	"hash/fnv"
	"sort"
)

// HashRing maps keys to nodes using a sorted ring of virtual-node hash points.
type HashRing struct {
	replicas int
	points   []uint64          // sorted virtual-node positions
	owner    map[uint64]string // position -> real node
	nodes    map[string]bool
}

// NewHashRing builds an empty ring with the given number of virtual nodes per
// real node.
func NewHashRing(replicas int) *HashRing {
	if replicas < 1 {
		replicas = 1
	}
	return &HashRing{
		replicas: replicas,
		owner:    make(map[uint64]string),
		nodes:    make(map[string]bool),
	}
}

func hashKey(s string) uint64 {
	h := fnv.New64a()
	_, _ = h.Write([]byte(s))
	return fmix64(h.Sum64())
}

// fmix64 is the murmur3 finalizer; FNV-1a alone has weak avalanche on short,
// similar strings (e.g. "n0#0" vs "n1#0"), which clusters virtual nodes and
// unbalances the ring. The finalizer spreads them.
func fmix64(h uint64) uint64 {
	h ^= h >> 33
	h *= 0xff51afd7ed558ccd
	h ^= h >> 33
	h *= 0xc4ceb9fe1a85ec53
	h ^= h >> 33
	return h
}

// Add inserts a node and its virtual nodes into the ring.
func (r *HashRing) Add(node string) {
	if r.nodes[node] {
		return
	}
	r.nodes[node] = true
	for i := 0; i < r.replicas; i++ {
		p := hashKey(node + "#" + itoa(i))
		r.owner[p] = node
		r.points = append(r.points, p)
	}
	sort.Slice(r.points, func(a, b int) bool { return r.points[a] < r.points[b] })
}

// Remove deletes a node and its virtual nodes from the ring.
func (r *HashRing) Remove(node string) {
	if !r.nodes[node] {
		return
	}
	delete(r.nodes, node)
	kept := r.points[:0]
	for _, p := range r.points {
		if r.owner[p] == node {
			delete(r.owner, p)
			continue
		}
		kept = append(kept, p)
	}
	r.points = kept
}

// Get returns the node that owns the given key, or "" if the ring is empty.
func (r *HashRing) Get(key string) string {
	if len(r.points) == 0 {
		return ""
	}
	h := hashKey(key)
	// first ring point >= h, wrapping around to the start.
	idx := sort.Search(len(r.points), func(i int) bool { return r.points[i] >= h })
	if idx == len(r.points) {
		idx = 0
	}
	return r.owner[r.points[idx]]
}

// NodeCount returns the number of real nodes currently on the ring.
func (r *HashRing) NodeCount() int { return len(r.nodes) }

// itoa is a tiny dependency-free int->string (avoids importing strconv twice).
func itoa(i int) string {
	if i == 0 {
		return "0"
	}
	var buf [20]byte
	pos := len(buf)
	neg := i < 0
	if neg {
		i = -i
	}
	for i > 0 {
		pos--
		buf[pos] = byte('0' + i%10)
		i /= 10
	}
	if neg {
		pos--
		buf[pos] = '-'
	}
	return string(buf[pos:])
}
