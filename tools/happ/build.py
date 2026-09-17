#!/usr/bin/env python3
"""Build and audit local Happ Geo databases; no downloads or publication."""

import argparse
import base64
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
PINS = {
    "geosite": ("github.com/v2fly/domain-list-community", "6f3acc3ba95299031cf408232e2e65e2c892fd2d"),
    "geoip": ("github.com/Loyalsoldier/geoip", "1503074d8aee4c623791210e90c04d586c86c8f7"),
}
DOMAIN_TYPES = {"DOMAIN": "full", "DOMAIN-SUFFIX": "domain", "DOMAIN-KEYWORD": "keyword"}
SKIPPED = {
    "IP-ASN": "ASN excluded",
    "AND": "compound condition cannot be represented in Geo",
    "OR": "compound condition excluded; not expanded",
    "USER-AGENT": "user-agent condition cannot be represented in Geo",
    "PROCESS-NAME": "process condition cannot be represented in Geo",
    "URL-REGEX": "URL condition cannot be represented in Geo",
}
TEMPLATE_CATEGORIES = {"openai", "telegram", "advertisinglite"}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_rule(raw):
    """Return (type, converted value, warning, skip reason) for one physical line."""
    if any(ord(c) < 32 and c != "\t" for c in raw):
        raise ValueError("control character in rule")
    line = raw.strip()
    if not line or line.startswith("#"):
        return None
    fields = [p.strip() for p in line.split(",")]
    kind = fields[0]
    if kind in {"AND", "OR"}:
        if len(fields) < 2 or not line.partition(",")[2].strip():
            raise ValueError("missing compound condition")
        return kind, None, None, SKIPPED[kind]
    if kind not in DOMAIN_TYPES and kind not in {"IP-CIDR", "IP-CIDR6"} and kind not in SKIPPED:
        raise ValueError(f"unknown rule type: {kind}")
    is_ip = kind in {"IP-CIDR", "IP-CIDR6", "IP-ASN"}
    if len(fields) not in ({2, 3} if is_ip else {2}) or not fields[1]:
        raise ValueError(f"invalid field count or empty value for {kind}")
    if len(fields) == 3 and fields[2] != "no-resolve":
        raise ValueError(f"unknown modifier: {fields[2]}")
    if kind in SKIPPED:
        return kind, None, None, SKIPPED[kind]
    value = fields[1]
    if kind in DOMAIN_TYPES:
        # Restrict compiler grammar, not keywords to complete DNS names.
        if not re.fullmatch(r"[A-Za-z0-9.-]+", value):
            raise ValueError("unsafe/unsupported domain characters (use ASCII or punycode)")
        if kind != "DOMAIN-KEYWORD" and (
            len(value) > 253 or any(
                not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
                for label in value.split(".")
            )
        ):
            raise ValueError("invalid domain name")
        return kind, DOMAIN_TYPES[kind] + ":" + value.lower(), None, None
    if "/" not in value or "%" in value:
        raise ValueError("unscoped CIDR with prefix length required")
    network = ipaddress.ip_network(value, strict=True)
    if network.version != (6 if kind == "IP-CIDR6" else 4):
        raise ValueError(f"address family does not match {kind}")
    warning = "no-resolve removed; Geo cannot preserve per-rule DNS behavior" if len(fields) == 3 else None
    return kind, str(network), warning, None


def category_paths(categories, root=ROOT):
    names = set()
    paths = []
    rules = (root / "rule/Surge").resolve()
    for category in categories:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", category):
            raise ValueError(f"invalid category name: {category!r}")
        name = category.lower()
        if name in names:
            raise ValueError(f"duplicate/lowercase category collision: {category}")
        names.add(name)
        path = (rules / category / (category + ".list")).resolve()
        if not path.is_relative_to(rules) or not path.is_file():
            raise ValueError(f"missing or out-of-tree category: {path}")
        paths.append((name, path))
    return paths


def convert_category(path):
    sites, ips = set(), set()
    counts = {}
    skipped, warnings = [], []
    data = path.read_bytes()
    for number, raw in enumerate(data.decode("utf-8").split("\n"), 1):
        # Accept CRLF, but not embedded control characters.
        raw = raw.removesuffix("\r")
        try:
            rule = parse_rule(raw)
        except ValueError as exc:
            raise ValueError(f"{path}:{number}: {exc}: {raw!r}") from exc
        if rule is None:
            continue
        kind, value, warning, reason = rule
        count = counts.setdefault(kind, {"read": 0, "converted": 0, "skipped": 0})
        count["read"] += 1
        source = {"path": str(path), "line": number, "text": raw}
        if reason:
            skipped.append({**source, "reason": reason})
            count["skipped"] += 1
        else:
            (sites if kind in DOMAIN_TYPES else ips).add(value)
            count["converted"] += 1
            if warning:
                warnings.append({**source, "reason": warning})
    if not sites and not ips:
        raise ValueError(f"{path}: category has no supported rules")
    stats = {
        "input": str(path), "sha256": hashlib.sha256(data).hexdigest(),
        "by_rule_type": counts, "skipped": skipped, "warnings": warnings,
        "before_compile": {"geosite": len(sites), "geoip": len(ips)},
        "duplicates_removed": sum(v["converted"] for v in counts.values()) - len(sites) - len(ips),
    }
    return sites, ips, stats


def require_both_inputs(sites, ips):
    for label, entries in (("domain", sites), ("CIDR", ips)):
        if not entries:
            raise ValueError(f"no {label} input: add a category containing supported {label} rules; this command builds both databases")


def prepare_output(path):
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise ValueError(f"output must be an empty directory: {path}")
    path.mkdir(parents=True, exist_ok=True)


def tool_info(path, kind):
    path = path.resolve()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError(f"tool is not executable: {path}")
    result = subprocess.run(["go", "version", "-m", str(path)], capture_output=True, text=True, check=True)
    info = result.stdout
    if kind in PINS:
        module, commit = PINS[kind]
        if f"\tpath\t{module}\n" not in info or f"vcs.revision={commit}\n" not in info or "vcs.modified=false\n" not in info:
            raise ValueError(f"{path}: expected clean pinned build of {module}@{commit}; see README")
    else:
        for module, version in (("github.com/v2fly/v2ray-core/v5", "v5.42.0"), ("google.golang.org/protobuf", "v1.36.11")):
            if f"\tdep\t{module}\t{version}\t" not in info:
                raise ValueError(f"{path}: reader must use {module}@{version}")
    return {"path": str(path), "sha256": sha256(path), "go_build_info": info,
            **({"source": "https://" + PINS[kind][0], "commit": PINS[kind][1]} if kind in PINS else {})}


def run_tool(command, output, label, commands):
    result = subprocess.run([str(v) for v in command], capture_output=True, text=True)
    log = output / (label + ".log")
    log.write_text(result.stdout + result.stderr, encoding="utf-8")
    commands.append({"argv": [str(v) for v in command], "returncode": result.returncode, "log": str(log)})
    if result.returncode:
        raise ValueError(f"{label} exited {result.returncode}; see {log}: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout


def collapse(cidrs):
    networks = [ipaddress.ip_network(c, strict=True) for c in cidrs]
    return [str(n) for version in (4, 6) for n in ipaddress.collapse_addresses(
        n for n in networks if n.version == version)]


def verify_readback(decoded, sites, ips):
    """Compare full typed domain sets and canonical CIDR unions, not just counts."""
    actual_sites, actual_ips = {}, {}
    types = {"Full": "full", "RootDomain": "domain", "Plain": "keyword"}
    for entry in decoded["geosite"].get("entry", []):
        name = entry["countryCode"].lower()
        if name in actual_sites:
            raise ValueError(f"duplicate geosite category: {name}")
        values = []
        for domain in entry.get("domain", []):
            if domain.get("attribute") or domain.get("type", "Plain") not in types:
                raise ValueError(f"unexpected domain type/attribute: {name}: {domain}")
            values.append(types[domain.get("type", "Plain")] + ":" + domain["value"])
        if len(values) != len(set(values)):
            raise ValueError(f"duplicate domain entries: {name}")
        actual_sites[name] = set(values)
    for entry in decoded["geoip"].get("entry", []):
        name = entry["countryCode"].lower()
        if name in actual_ips or entry.get("reverseMatch"):
            raise ValueError(f"duplicate/reversed geoip category: {name}")
        actual_ips[name] = [str(ipaddress.ip_network((
            ipaddress.ip_address(base64.b64decode(cidr["ip"], validate=True)), cidr.get("prefix", 0)
        ), strict=True)) for cidr in entry.get("cidr", [])]
    if actual_sites != sites:
        raise ValueError("geosite readback differs from input category/type/value sets")
    if set(actual_ips) != set(ips):
        raise ValueError("geoip readback category set differs from input")
    for name in ips:
        if collapse(ips[name]) != collapse(actual_ips[name]):
            raise ValueError(f"geoip readback coverage differs: {name}")
    return {name: {"geosite": len(actual_sites.get(name, [])), "geoip": len(actual_ips.get(name, [])),
                   "geoip_ipv4": sum(ipaddress.ip_network(n).version == 4 for n in actual_ips.get(name, [])),
                   "geoip_ipv6": sum(ipaddress.ip_network(n).version == 6 for n in actual_ips.get(name, []))}
            for name in sites.keys() | ips.keys()}


def validate_url(url):
    try:
        parts = urlsplit(url)
        if (parts.scheme not in {"http", "https"} or not parts.hostname or parts.username is not None
                or parts.password is not None or parts.fragment or "\\" in url
                or re.search(r"%(?![0-9A-Fa-f]{2})", url)
                or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in url)):
            raise ValueError("expected HTTP(S) URL without credentials, whitespace or fragment")
        if parts.port is not None and not 1 <= parts.port <= 65535:
            raise ValueError("invalid port")
        host = parts.hostname
        if ":" in host:
            ipaddress.IPv6Address(host)
        elif not re.fullmatch(r"[A-Za-z0-9.-]+", host) or any(
            not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
            for label in host.rstrip(".").split(".")
        ) or len(host) > 253:
            raise ValueError("invalid hostname")
    except ValueError as exc:
        raise ValueError(f"invalid Geo URL: {exc}") from exc
    return url


def routing_profile(categories, sites, ips, geosite_url, geoip_url):
    if not TEMPLATE_CATEGORIES.issubset(categories):
        raise ValueError("test profile requires OpenAI, Telegram and AdvertisingLite")
    profile = {
        "Name": "ios_rule_script-local-test", "GlobalProxy": "true",
        "RemoteDNSType": "DoH", "RemoteDNSDomain": "https://cloudflare-dns.com/dns-query", "RemoteDNSIP": "1.1.1.1",
        "DomesticDNSType": "DoH", "DomesticDNSDomain": "https://dns.google/dns-query", "DomesticDNSIP": "8.8.8.8",
        "Geositeurl": validate_url(geosite_url), "Geoipurl": validate_url(geoip_url),
        "DnsHosts": {"cloudflare-dns.com": "1.1.1.1", "dns.google": "8.8.8.8"},
        "DomainStrategy": "AsIs", "FakeDNS": "false", "LastUpdated": "",
        "DirectSites": [], "DirectIp": [],
    }
    for action, names in (("Proxy", ["openai", "telegram"]), ("Block", ["advertisinglite"])):
        profile[action + "Sites"] = ["geosite:" + n for n in names if n in sites]
        profile[action + "Ip"] = ["geoip:" + n for n in names if n in ips]
    return profile


def write_profile(output, profile):
    write_json(output / "routing.json", profile)
    data = (output / "routing.json").read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    if json.loads(base64.b64decode(encoded, validate=True)) != profile:
        raise ValueError("routing Base64 roundtrip failed")
    (output / "routing.txt").write_text("happ://routing/add/" + encoded + "\n", encoding="utf-8")


def build(args):
    if (args.geosite_url is None) != (args.geoip_url is None):
        raise ValueError("--geosite-url and --geoip-url must be supplied together")
    output = args.output.resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError(f"output must be an empty directory: {output}")
    sites, ips, categories = {}, {}, {}
    for name, path in category_paths(args.categories):
        domains, networks, stats = convert_category(path)
        categories[name] = stats
        if domains:
            sites[name] = domains
        if networks:
            ips[name] = networks
    require_both_inputs(sites, ips)
    profile = routing_profile(categories, sites, ips, args.geosite_url, args.geoip_url) if args.geosite_url is not None else None
    tools = {kind: tool_info(path, kind) for kind, path in (
        ("geosite", args.geosite_tool), ("geoip", args.geoip_tool), ("reader", args.geo_reader))}
    prepare_output(output)
    report = {"status": "building", "categories": categories, "tools": tools, "commands": []}
    try:
        for filename, entries in (("geosite-input", sites), ("geoip-input", ips)):
            directory = output / filename
            directory.mkdir()
            for name, values in entries.items():
                (directory / name).write_text("\n".join(sorted(values)) + "\n", encoding="utf-8")
        config = {
            "input": [{"type": "text", "action": "add", "args": {"name": name, "uri": str(output / "geoip-input" / name)}} for name in ips],
            "output": [{"type": "v2rayGeoIPDat", "action": "output", "args": {"outputDir": str(output), "outputName": "geoip.dat"}}],
        }
        write_json(output / "geoip-config.json", config)
        run_tool([tools["geosite"]["path"], "--datapath=" + str(output / "geosite-input"),
                  "--outputdir=" + str(output), "--outputname=geosite.dat"], output, "geosite-build", report["commands"])
        run_tool([tools["geoip"]["path"], "convert", "-c", output / "geoip-config.json"], output, "geoip-build", report["commands"])
        for filename in ("geosite.dat", "geoip.dat"):
            if not (output / filename).is_file() or not (output / filename).stat().st_size:
                raise ValueError(f"compiler did not produce a nonempty {filename}")
        decoded = json.loads(run_tool([tools["reader"]["path"], output / "geosite.dat", output / "geoip.dat"], output, "readback", report["commands"]))
        write_json(output / "readback.json", decoded)
        after = verify_readback(decoded, sites, ips)
        for name, counts in after.items():
            categories[name]["after_compile"] = counts
        if profile:
            write_profile(output, profile)
        report["status"] = "validated"
        report["validation"] = {"category_sets": "equal", "domain_types_and_values": "equal", "cidr_coverage": "equal"}
        report["artifacts"] = {f: {"bytes": (output / f).stat().st_size, "sha256": sha256(output / f)} for f in ("geosite.dat", "geoip.dat")}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report["status"] = "failed"
        report["error"] = str(exc)
        raise
    finally:
        write_json(output / "conversion-report.json", report)
    converted = sum(v["converted"] for c in categories.values() for v in c["by_rule_type"].values())
    skipped = sum(len(c["skipped"]) for c in categories.values())
    print(f"Validated {output}: converted {converted} input lines; skipped {skipped}; Happ device validation pending")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build both Happ Geo databases locally. Selected categories together must contain domains and CIDRs. Requires Go for pinned tool metadata verification.")
    parser.add_argument("--categories", nargs="+", required=True, help="Surge main-file category names (case-sensitive)")
    parser.add_argument("--geosite-tool", type=Path, required=True)
    parser.add_argument("--geoip-tool", type=Path, required=True)
    parser.add_argument("--geo-reader", type=Path, required=True, help="read-only helper built as documented in README")
    parser.add_argument("--output", type=Path, required=True, help="new or empty output directory")
    parser.add_argument("--geosite-url", help="optional HTTP(S) URL; requires --geoip-url and all three test categories")
    parser.add_argument("--geoip-url")
    args = parser.parse_args(argv)
    try:
        build(args)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
