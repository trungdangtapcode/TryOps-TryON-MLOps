package main

import (
	"log"
	"net/http"
)

func main() {
	server := newControllerServer()
	log.Printf("tryops-controller listening on %s", server.Addr)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}
