#!/usr/bin/env python3
"""Actions-only rule snapshot and compact release metadata; no network or publication."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess

from build import PINS, sha256, write_json


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def commit_sha(value):
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("expected a full commit SHA")
    if git("rev-parse", value + "^{commit}") != value:
        raise ValueError("commit SHA mismatch")
    return value


def snapshot(source):
    """Replace only rule/ in a clean disposable checkout, including deletions."""
    commit_sha(source)
    if git("status", "--porcelain", "--untracked-files=all"):
        raise ValueError("snapshot requires a clean disposable checkout")
    if git("ls-files", "--others", "--ignored", "--exclude-standard", "--", "rule/"):
        raise ValueError("ignored files in rule/ would contaminate the snapshot")
    if git("cat-file", "-t", source + ":rule") != "tree":
        raise ValueError("upstream rule/ must be a tree")
    entries = git("ls-tree", "-r", source, "--", "rule/").splitlines()
    if not entries or any(line.split()[0] not in {"100644", "100755"} for line in entries):
        raise ValueError("upstream rule/ must contain only regular files, not symlinks/gitlinks")
    # No upstream checkout/merge: self-owned files and executable code stay untouched.
    subprocess.run(["git", "restore", "--source=" + source, "--staged", "--worktree", "--", "rule/"], check=True)
    verify_tree(source)


def verify_tree(source):
    commit_sha(source)
    if git("rev-parse", git("write-tree") + ":rule") != git("rev-parse", source + ":rule"):
        raise ValueError("staged rule tree differs from pinned upstream")
    if git("diff", "--name-only") or git("ls-files", "--others", "--exclude-standard"):
        raise ValueError("unexpected unstaged/untracked changes")
    changed = git("diff", "--cached", "--name-only", "-z").split("\0")
    if any(path and not path.startswith("rule/") for path in changed):
        raise ValueError("staged changes outside rule/")


def validated_report(output):
    report = json.loads((output / "conversion-report.json").read_text())
    if (report["status"] != "validated" or report["selection"] != "all" or report["validation"] != {
            "category_sets": "equal", "domain_types_and_values": "equal", "cidr_coverage": "equal"}):
        raise ValueError("release requires a validated full build and all readback checks")
    for name in ("geosite.dat", "geoip.dat"):
        path = output / name
        if report["artifacts"][name] != {"bytes": path.stat().st_size, "sha256": sha256(path)} or not path.stat().st_size:
            raise ValueError("artifact differs from validated build: " + name)
    for kind, (module, revision) in PINS.items():
        if report["tools"][kind]["commit"] != revision or report["tools"][kind]["source"] != "https://" + module:
            raise ValueError("compiler pin mismatch: " + kind)
    for category in report["categories"].values():
        path = Path(category["input"])
        if not path.resolve().is_relative_to((Path.cwd() / "rule/Surge").resolve()) or sha256(path) != category["sha256"]:
            raise ValueError("source differs from validated build: " + str(path))
    return report


def manifest(source, base, target, output, run_id, attempt):
    verify_tree(source)
    report = validated_report(output)
    for value in (base, target):
        commit_sha(value)
    if git("rev-parse", "HEAD") != target or git("rev-parse", target + ":rule") != git("rev-parse", source + ":rule"):
        raise ValueError("release target must be the actual synchronized HEAD")
    reasons = Counter(item["reason"] for category in report["categories"].values() for item in category["skipped"])
    warnings = sum(len(category["warnings"]) for category in report["categories"].values())
    mapped = sum(count for reason, count in reasons.items() if reason.startswith("IPv4-mapped IPv6"))
    changes = Counter(line[0] for line in git("diff", "--no-renames", "--name-status", base, target, "--", "rule/").splitlines())
    limitations = [
        "Geo stores match sets, not routing actions; Happ device compatibility is not yet verified.",
        "ASN, compound conditions, user-agent, process and URL rules are skipped, not approximated.",
        f"IPv4-mapped IPv6 skipped: {mapped} lines (historical baseline 116); never converted to IPv4.",
        f"Per-rule no-resolve cannot be preserved: {warnings} warnings.",
        "Full means all discovered Surge categories audited, not lossless conversion of every rule.",
    ]
    data = {
        "upstream_repository": "blackmatrix7/ios_rule_script", "upstream_ref": "master", "source_commit": source,
        "repository": "lay-g/ios_rule_script", "checkout_commit": base, "target_commit": target,
        "run_id": run_id, "run_attempt": attempt, "sync_scope": "rule/", "happ_input": "rule/Surge (all, prefer _All)",
        "rule_files_changed": dict(changes), "summary": report["summary"], "validation": report["validation"],
        "tools": report["tools"], "artifacts": report["artifacts"], "skipped_by_reason": dict(reasons),
        "mapped_ipv6_skipped_lines": mapped, "no_resolve_warnings": warnings, "limitations": limitations,
    }
    # Local paths are diagnostics, not part of the public tool identity.
    data["tools"] = {kind: {k: v for k, v in info.items() if k != "path"} for kind, info in data["tools"].items()}
    write_json(output / "build-manifest.json", data)
    notes = ["# Happ full rule snapshot", "", f"- Source: blackmatrix7/ios_rule_script@{source} (master)",
             f"- Checkout: {base}", f"- Target: lay-g/ios_rule_script@{target}", f"- Run: {run_id}, attempt: {attempt}",
             f"- All-client rule/ file changes: {dict(changes) or 'none (no empty commit)'}",
             f"- Converted: {report['summary']['converted_lines']}; skipped: {report['summary']['skipped_lines']} input lines.",
             "- Compiler pins: " + "; ".join(module + "@" + revision for module, revision in PINS.values()),
             "", "## Limitations", *["- " + value for value in limitations], "",
             "Data snapshot, not an application semantic-version release. Multiple same-day releases and identical data are intentional; no history is automatically deleted.",
             "Full per-line diagnostics/readback are in the Actions artifact, not release attachments.", "",
             "## Stable Happ downloads", "",
             "- https://github.com/lay-g/ios_rule_script/releases/latest/download/geosite.dat",
             "- https://github.com/lay-g/ios_rule_script/releases/latest/download/geoip.dat", ""]
    (output / "release-notes.md").write_text("\n".join(notes))
    names = ("geosite.dat", "geoip.dat", "build-manifest.json", "release-notes.md")
    (output / "SHA256SUMS").write_text("".join(f"{sha256(output / name)}  {name}\n" for name in names))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("snapshot", "verify", "manifest"):
        command = sub.add_parser(name)
        command.add_argument("--source", required=True)
        if name != "snapshot":
            command.add_argument("--output", required=True, type=Path)
        if name == "manifest":
            for flag in ("base", "target", "run-id", "attempt"):
                command.add_argument("--" + flag, required=True)
    args = parser.parse_args()
    if args.command == "snapshot":
        snapshot(args.source)
    elif args.command == "verify":
        verify_tree(args.source)
        validated_report(args.output)
    else:
        manifest(args.source, args.base, args.target, args.output, args.run_id, args.attempt)


if __name__ == "__main__":
    main()
