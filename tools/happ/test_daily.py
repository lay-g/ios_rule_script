"""Disposable Git fixtures and the actual workflow shell; never use the real origin."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

import build
import daily

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / ".github/workflows/happ-daily.yml").read_text()


def step_shell(name):
    section = WORKFLOW.split("      - name: " + name + "\n", 1)[1].split("      - name:", 1)[0]
    match = re.search(r"        run: \|\n((?:          .*\n|\n)+)", section)
    return "\n".join(line[10:] for line in match[1].splitlines())


COMMIT = "Verify, commit only changed rules, and prepare compact release metadata"
PUSH = "Normal push; abort on external advancement (never force or rebase)"
RELEASE = "Upload a draft completely, then publish as latest"


class DailyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "fork"
        self.repo.mkdir()
        self.previous = Path.cwd()
        os.chdir(self.repo)
        self.addCleanup(os.chdir, self.previous)
        self.git("init", "--initial-branch=main")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        for path, text in {"rule/Surge/Sample/Sample.list": "DOMAIN,example.com\nIP-CIDR,192.0.2.1\n",
                           "rule/Clash/old.yaml": "old\n", "rule/QuantumultX/keep.list": "old\n",
                           "tools/own.txt": "own", ".github/own.txt": "own", "docs/own.txt": "own",
                           "rewrite/own.txt": "own", "script/own.txt": "own"}.items():
            self.put(path, text)
        for name in ("build.py", "daily.py"):
            self.put("tools/happ/" + name, (ROOT / "tools/happ" / name).read_text())
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.base = daily.git("rev-parse", "HEAD")
        self.remote = self.root / "remote.git"
        self.git("clone", "--bare", str(self.repo), str(self.remote))
        self.git("remote", "add", "origin", str(self.remote))
        # Simulate an upstream commit in the local object database, never a real remote.
        self.put("rule/Surge/Sample/Sample.list", "DOMAIN,new.example\nIP-CIDR6,2001:db8::1\n")
        (self.repo / "rule/Clash/old.yaml").unlink()
        self.put("rule/Clash/New/new.yaml", "new client rule\n")
        self.put("rule/QuantumultX/keep.list", "changed\n")
        self.put("rule/NewClient/new.txt", "new client\n")
        for name in ("tools", ".github", "docs", "rewrite", "script"):
            self.put(name + "/own.txt", "upstream must not overwrite this")
        self.git("add", ".")
        self.git("commit", "-qm", "upstream")
        self.source = daily.git("rev-parse", "HEAD")
        self.git("checkout", "--detach", self.base)
        self.output = self.root / "output"
        self.output.mkdir()
        self.env = {**os.environ, "SOURCE_SHA": self.source, "BASE_SHA": self.base,
                    "DEFAULT_BRANCH": "main", "OUT": str(self.output), "GITHUB_RUN_ID": "123",
                    "GITHUB_RUN_ATTEMPT": "1", "GITHUB_OUTPUT": str(self.root / "step-output")}

    def git(self, *args):
        return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()

    def put(self, path, text):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def shell(self, name, extra="", env=None):
        return subprocess.run(["bash", "-e", "-o", "pipefail", "-c", step_shell(name) + "\n" + extra],
                              env=env or self.env, capture_output=True, text=True)

    def report(self):
        # Compiler behavior is covered by test_build and real builds, not this Git fixture.
        for name in ("geosite.dat", "geoip.dat"):
            (self.output / name).write_bytes(b"fixture dat")
        path = self.repo / "rule/Surge/Sample/Sample.list"
        report = {"status": "validated", "selection": "all", "validation": {
            "category_sets": "equal", "domain_types_and_values": "equal", "cidr_coverage": "equal"},
            "artifacts": {name: {"bytes": (self.output / name).stat().st_size, "sha256": build.sha256(self.output / name)}
                          for name in ("geosite.dat", "geoip.dat")},
            "tools": {kind: {"source": "https://" + module, "commit": sha} for kind, (module, sha) in build.PINS.items()},
            "summary": {"converted_lines": 2, "skipped_lines": 1},
            "categories": {"sample": {"input": str(path), "sha256": build.sha256(path), "warnings": [],
                                      "skipped": [{"reason": "IPv4-mapped IPv6 cannot be preserved by pinned GeoIP compiler; not converted to IPv4"}]}}}
        build.write_json(self.output / "conversion-report.json", report)
        return report

    def test_snapshot_all_clients_and_commit_target_preserve_own_files(self):
        daily.snapshot(self.source)
        self.assertEqual(daily.git("rev-parse", daily.git("write-tree") + ":rule"), daily.git("rev-parse", self.source + ":rule"))
        for name in ("tools", ".github", "docs", "rewrite", "script"):
            self.assertEqual((self.repo / name / "own.txt").read_text(), "own")
        self.assertFalse((self.repo / "rule/Clash/old.yaml").exists())
        self.report()
        result = self.shell(COMMIT)
        self.assertEqual(result.returncode, 0, result.stderr)
        target = daily.git("rev-parse", "HEAD")
        self.assertNotEqual(target, self.base)
        self.assertEqual(daily.git("rev-parse", "HEAD^"), self.base)
        self.env["TARGET_SHA"] = target
        result = self.shell(PUSH)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("--git-dir=" + str(self.remote), "rev-parse", "main"), target)
        data = json.loads((self.output / "build-manifest.json").read_text())
        self.assertEqual(data["target_commit"], target)
        self.assertEqual(data["mapped_ipv6_skipped_lines"], 1)
        self.assertEqual(data["rule_files_changed"], {"A": 2, "D": 1, "M": 2})

    def test_no_changes_no_empty_commit_but_metadata_and_push_check_succeed(self):
        daily.snapshot(self.base)
        self.env["SOURCE_SHA"] = self.base
        self.report()
        result = self.shell(COMMIT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(daily.git("rev-parse", "HEAD"), self.base)
        self.env["TARGET_SHA"] = self.base
        self.assertEqual(self.shell(PUSH).returncode, 0)
        self.assertEqual(json.loads((self.output / "build-manifest.json").read_text())["rule_files_changed"], {})

    def test_failed_readback_partial_build_or_tampering_prevents_commit(self):
        daily.snapshot(self.source)
        for mutation in ("missing", "failed", "partial", "readback", "artifact", "source"):
            with self.subTest(mutation=mutation):
                report = self.report()
                if mutation == "missing":
                    (self.output / "conversion-report.json").unlink()
                elif mutation == "artifact":
                    (self.output / "geoip.dat").write_bytes(b"corrupt")
                elif mutation == "source":
                    report["categories"]["sample"]["sha256"] = "bad"
                elif mutation == "failed":
                    report["status"] = "failed"
                elif mutation == "partial":
                    report["selection"] = "explicit"
                else:
                    report["validation"]["cidr_coverage"] = "different"
                if mutation not in {"missing", "artifact"}:
                    build.write_json(self.output / "conversion-report.json", report)
                self.assertNotEqual(self.shell(COMMIT).returncode, 0)
                self.assertEqual(daily.git("rev-parse", "HEAD"), self.base)
                self.assertEqual(self.git("--git-dir=" + str(self.remote), "rev-parse", "main"), self.base)

    def test_dirty_checkout_and_symlink_source_rejected(self):
        self.put("docs/untracked", "preserve")
        with self.assertRaisesRegex(ValueError, "clean"):
            daily.snapshot(self.source)
        (self.repo / "docs/untracked").unlink()
        (self.repo / "rule/link").symlink_to("../tools")
        self.git("add", "rule/link")
        self.git("commit", "-qm", "unsafe source")
        unsafe = daily.git("rev-parse", "HEAD")
        self.git("checkout", "--detach", self.base)
        with self.assertRaisesRegex(ValueError, "regular files"):
            daily.snapshot(unsafe)
        self.assertEqual(daily.git("status", "--porcelain"), "")

    def test_external_push_race_rejected_without_rebase_or_release(self):
        daily.snapshot(self.source)
        self.report()
        self.assertEqual(self.shell(COMMIT).returncode, 0)
        self.env["TARGET_SHA"] = daily.git("rev-parse", "HEAD")
        actor = self.root / "actor"
        self.git("clone", str(self.remote), str(actor))
        self.git("-C", str(actor), "config", "user.name", "Actor")
        self.git("-C", str(actor), "config", "user.email", "actor@example.invalid")
        self.git("-C", str(actor), "commit", "--allow-empty", "-qm", "external advance")
        wrappers = self.root / "bin"
        wrappers.mkdir()
        real_git = shutil.which("git")
        wrapper = wrappers / "git"
        wrapper.write_text(f'#!/bin/bash\nset -e\n"{real_git}" "$@"\n'
                           f'if [ "$1" = ls-remote ] && [ ! -e "{self.root}/raced" ]; then\n'
                           f'  touch "{self.root}/raced"\n  "{real_git}" -C "{actor}" push origin main >&2\nfi\n')
        wrapper.chmod(0o755)
        env = {**self.env, "PATH": str(wrappers) + os.pathsep + os.environ["PATH"]}
        marker = self.root / "release-reached"
        result = self.shell(PUSH, f'touch "{marker}"', env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rejected", result.stderr)
        self.assertFalse(marker.exists())
        self.assertEqual(daily.git("rev-parse", "HEAD"), self.env["TARGET_SHA"])
        self.assertEqual(self.git("--git-dir=" + str(self.remote), "rev-parse", "main"),
                         self.git("-C", str(actor), "rev-parse", "HEAD"))
        # Also reject an already-advanced remote when there are no local rule changes.
        self.env["TARGET_SHA"] = self.base
        self.assertNotEqual(self.shell(PUSH).returncode, 0)

    def test_rerun_old_base_after_successful_push_requires_new_dispatch(self):
        daily.snapshot(self.source)
        self.report()
        result = self.shell(COMMIT)
        self.assertEqual(result.returncode, 0, result.stderr)
        pushed = daily.git("rev-parse", "HEAD")
        self.env["TARGET_SHA"] = pushed
        self.assertEqual(self.shell(PUSH).returncode, 0)
        # GitHub Re-run keeps github.sha even after the prior attempt pushed rules.
        self.git("checkout", "--detach", self.base)
        self.env["GITHUB_RUN_ATTEMPT"] = "2"
        daily.snapshot(self.source)
        self.report()
        result = self.shell(COMMIT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.env["TARGET_SHA"] = daily.git("rev-parse", "HEAD")
        marker = self.root / "rerun-release-reached"
        result = self.shell(PUSH, f'touch "{marker}"')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists())
        self.assertEqual(self.git("--git-dir=" + str(self.remote), "rev-parse", "main"), pushed)

    def test_release_upload_failure_stays_draft_and_attempts_have_unique_tags(self):
        daily.snapshot(self.base)
        self.report()
        daily.manifest(self.base, self.base, self.base, self.output, "123", "1")
        wrappers = self.root / "bin"
        wrappers.mkdir()
        log = self.root / "gh.log"
        gh = wrappers / "gh"
        gh.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$GH_LOG"\n'
                      'if [ "$2" = upload ] && [ "$FAIL_UPLOAD" = 1 ]; then exit 9; fi\n')
        gh.chmod(0o755)
        env = {**self.env, "TARGET_SHA": self.base, "GH_LOG": str(log), "FAIL_UPLOAD": "1",
               "PATH": str(wrappers) + os.pathsep + os.environ["PATH"]}
        self.assertNotEqual(self.shell(RELEASE, env=env).returncode, 0)
        self.assertNotIn("release edit", log.read_text())
        self.assertIn("--draft", log.read_text())
        self.assertIn("--target " + self.base, log.read_text())
        env.update(FAIL_UPLOAD="0", GITHUB_RUN_ATTEMPT="2")
        self.assertEqual(self.shell(RELEASE, env=env).returncode, 0)
        lines = log.read_text().splitlines()
        tags = [line.split()[2] for line in lines if line.startswith("release create")]
        self.assertEqual(len(set(tags)), 2)
        self.assertTrue(lines[-1].endswith("--draft=false --latest"))
        upload = next(line for line in lines if line.startswith("release upload"))
        self.assertEqual(len(upload.split()), 8)  # command, subcommand, tag, five assets
        self.assertNotIn("readback", upload)


if __name__ == "__main__":
    unittest.main()
