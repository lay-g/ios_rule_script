// geo-reader only decodes databases using the compiler's existing protobuf API.
// Build from the pinned domain-list-community module; see README.md.
package main

import (
	"encoding/json"
	"fmt"
	"os"

	router "github.com/v2fly/v2ray-core/v5/app/router/routercommon"
	"google.golang.org/protobuf/encoding/protojson"
	"google.golang.org/protobuf/proto"
)

func decode(path string, message proto.Message) (json.RawMessage, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	if err := proto.Unmarshal(data, message); err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	return protojson.Marshal(message)
}

func run() error {
	if len(os.Args) != 3 {
		return fmt.Errorf("usage: geo-reader GEOSITE.dat GEOIP.dat")
	}
	sites, err := decode(os.Args[1], new(router.GeoSiteList))
	if err != nil {
		return err
	}
	ips, err := decode(os.Args[2], new(router.GeoIPList))
	if err != nil {
		return err
	}
	return json.NewEncoder(os.Stdout).Encode(map[string]json.RawMessage{
		"geosite": sites, "geoip": ips,
	})
}

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
