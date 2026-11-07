// Command avoar-core-gen generates consumer-local Go packages from Avoar contracts.
package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"path/filepath"

	core "github.com/avoarpj/core"
	"github.com/avoarpj/core/internal/gogen"
)

func main() {
	output := flag.String("output", "build/go", "directory for generated packages")
	prefix := flag.String("import-prefix", "", "Go import path corresponding to the output directory")
	clean := flag.Bool("clean", false, "remove only generated files from the output directory")
	flag.Parse()
	if flag.NArg() != 0 {
		fail(fmt.Errorf("unexpected positional arguments"))
	}
	absolute, err := filepath.Abs(*output)
	if err != nil {
		fail(err)
	}
	if *clean {
		if err := gogen.Clean(absolute); err != nil {
			fail(err)
		}
		return
	}
	if *prefix == "" {
		fail(fmt.Errorf("--import-prefix is required; see --help"))
	}
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()
	if err := gogen.Generate(ctx, core.Schemas, absolute, *prefix, gogen.RunPlugin); err != nil {
		fail(err)
	}
	fmt.Printf("Core Go gerado em %s\nRuntime: google.golang.org/protobuf %s\n", absolute, gogen.PluginVersion)
}

func fail(err error) {
	fmt.Fprintln(os.Stderr, "avoar-core-gen:", err)
	os.Exit(1)
}
