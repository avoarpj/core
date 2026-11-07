package gogen

import (
	"context"
	_ "embed"
	"errors"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"testing/fstest"

	core "github.com/avoarpj/core"
	"google.golang.org/protobuf/types/pluginpb"
)

//go:embed consumer_test.go.tmpl
var consumerTests []byte

func TestGeneratedConsumer(t *testing.T) {
	root := t.TempDir()
	output := filepath.Join(root, "generated")
	if err := Generate(context.Background(), core.Schemas, output, "example.com/consumer/generated", RunPlugin); err != nil {
		t.Fatal(err)
	}
	target := filepath.Join(output, "avoar/core/opendata/election/domain.pb.go")
	first, err := os.ReadFile(target)
	if err != nil {
		t.Fatal(err)
	}
	info, err := os.Stat(target)
	if err != nil {
		t.Fatal(err)
	}
	if err := Generate(context.Background(), core.Schemas, output, "example.com/consumer/generated", RunPlugin); err != nil {
		t.Fatal(err)
	}
	repeated, err := os.Stat(target)
	if err != nil || !repeated.ModTime().Equal(info.ModTime()) {
		t.Fatal("rewrote identical output", err)
	}
	if !strings.Contains(string(first), "example.com/consumer/generated") {
		t.Fatal("incorrect import mapping")
	}
	if err := os.WriteFile(filepath.Join(root, "go.mod"), []byte("module example.com/consumer\n\ngo 1.23.0\n\nrequire google.golang.org/protobuf "+PluginVersion+"\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "core_test.go"), consumerTests, 0o644); err != nil {
		t.Fatal(err)
	}
	command := exec.Command("go", "test", "-mod=mod", "./...")
	command.Dir = root
	if result, err := command.CombinedOutput(); err != nil {
		t.Fatalf("consumer tests: %v\n%s", err, result)
	}
	helper := filepath.Join(output, "handwritten.go")
	if err := os.WriteFile(helper, []byte("package handwritten\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := Clean(output); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(target); !os.IsNotExist(err) {
		t.Fatal("generated file not removed", err)
	}
	if _, err := os.Stat(helper); err != nil {
		t.Fatal("removed handwritten file", err)
	}
	if err := Clean(output); err != nil {
		t.Fatal(err)
	}
}

func TestFailurePreservesFiles(t *testing.T) {
	output := t.TempDir()
	target := filepath.Join(output, "owned.go")
	original := []byte(marker + "package previous\n")
	if err := os.WriteFile(target, original, 0o644); err != nil {
		t.Fatal(err)
	}
	failed := func(context.Context, *pluginpb.CodeGeneratorRequest) (*pluginpb.CodeGeneratorResponse, error) {
		return nil, errors.New("plugin failed")
	}
	if err := Generate(context.Background(), core.Schemas, output, "example.com/app/generated", failed); err == nil {
		t.Fatal("expected plugin failure")
	}
	if data, err := os.ReadFile(target); err != nil || string(data) != string(original) {
		t.Fatal("modified previous output", err)
	}
	invalid := fstest.MapFS{"avoar/core/opendata/example/domain.proto": {Data: []byte("invalid protobuf")}}
	if err := Generate(context.Background(), invalid, output, "example.com/app/generated", failed); err == nil {
		t.Fatal("expected compilation failure")
	}
	if data, err := os.ReadFile(target); err != nil || string(data) != string(original) {
		t.Fatal("modified previous output", err)
	}
}

func TestWriteProtectionAndStaleCleanup(t *testing.T) {
	root := t.TempDir()
	name := "avoar/core/opendata/example/domain.pb.go"
	target := filepath.Join(root, filepath.FromSlash(name))
	if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
		t.Fatal(err)
	}
	manual := []byte("package handwritten\n")
	if err := os.WriteFile(target, manual, 0o644); err != nil {
		t.Fatal(err)
	}
	outputs := map[string][]byte{name: []byte(marker + "package example\n")}
	if err := writeOutputs(root, outputs); err == nil {
		t.Fatal("overwrote user file")
	}
	if err := os.Remove(target); err != nil {
		t.Fatal(err)
	}
	stale := filepath.Join(root, "stale.go")
	if err := os.WriteFile(stale, []byte(marker+"package stale\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := writeOutputs(root, outputs); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(stale); !os.IsNotExist(err) {
		t.Fatal("stale output remains", err)
	}
	outside := t.TempDir()
	linked := filepath.Join(root, "linked")
	if err := os.Symlink(outside, linked); err != nil {
		t.Fatal(err)
	}
	if err := writeOutputs(linked, outputs); err == nil {
		t.Fatal("followed output symlink")
	}
}

func TestToolchainPin(t *testing.T) {
	if !strings.Contains(string(toolchainModule), "require google.golang.org/protobuf "+PluginVersion+"\n") {
		t.Fatal("plugin version and embedded toolchain disagree")
	}
}

func TestSourceDirectoryRejected(t *testing.T) {
	root := t.TempDir()
	name := filepath.Join(root, "avoar/core/opendata/example/domain.proto")
	if err := os.MkdirAll(filepath.Dir(name), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(name, []byte("schema"), 0o644); err != nil {
		t.Fatal(err)
	}
	schemas := fstest.MapFS{"avoar/core/opendata/example/domain.proto": {Data: []byte(`syntax = "proto3"; message Example {}`)}}
	if err := Generate(context.Background(), schemas, root, "example.com/app/generated", nil); err == nil {
		t.Fatal("accepted source tree as output")
	}
}

func TestInvalidPrefix(t *testing.T) {
	for _, prefix := range []string{"", "../bad", "/absolute", "example.com/a,b", "example.com/a//b"} {
		t.Run(prefix, func(t *testing.T) {
			if err := Generate(context.Background(), fs.FS(core.Schemas), t.TempDir(), prefix, nil); err == nil {
				t.Fatal("accepted invalid import prefix")
			}
		})
	}
}
