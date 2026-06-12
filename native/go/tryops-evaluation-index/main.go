package main

import (
	"encoding/json"
	"fmt"
	"os"
)

func main() {
	cfg := parseConfig()
	index, err := buildIndex(cfg.Root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "build evaluation index: %v\n", err)
		os.Exit(1)
	}
	if err := writeIndex(cfg.OutputPath, index); err != nil {
		fmt.Fprintf(os.Stderr, "write evaluation index: %v\n", err)
		os.Exit(2)
	}
	encoded, _ := json.Marshal(index)
	fmt.Println(string(encoded))
}
