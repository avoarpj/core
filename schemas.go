// Package core provides the canonical Avoar Protobuf schemas.
package core

import "embed"

// Schemas contains the contracts shipped with this version of the core.
//
//go:embed avoar/core/opendata/*/*.proto
var Schemas embed.FS
