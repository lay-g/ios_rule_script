import argparse
import base64
from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import ipaddress
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import build


def decoded_data(sites, ips):
    types = {"full": "Full", "domain": "RootDomain", "keyword": "Plain"}
    result = {"geosite": {"entry": []}, "geoip": {"entry": []}}
    for name, rules in sites.items():
        result["geosite"]["entry"].append({"countryCode": name.upper(), "domain": [
            {"type": types[v.split(":", 1)[0]], "value": v.split(":", 1)[1]} for v in sorted(rules)]})
    for name, rules in ips.items():
        result["geoip"]["entry"].append({"countryCode": name.upper(), "cidr": [
            {"ip": base64.b64encode(ipaddress.ip_network(v).network_address.packed).decode(),
             "prefix": ipaddress.ip_network(v).prefixlen} for v in sorted(rules)]})
    return result


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def source(self, name, text):
        path = self.root / "rule/Surge" / name / (name + ".list")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_convert_category_preserves_types_and_reports_lines(self):
        path = self.source("Sample", "# 注释\n\nDOMAIN,Example.COM\nDOMAIN,example.com\n"
                           "DOMAIN-SUFFIX,example.com\nDOMAIN-KEYWORD,.example-\nDOMAIN,192.0.2.1\n"
                           "IP-CIDR,192.0.2.0/24,no-resolve\nIP-CIDR6,2001:db8::/32,no-resolve\n"
                           "IP-ASN,123,no-resolve\nAND,((USER-AGENT,Frodo*),(DOMAIN,example.com))\n"
                           "OR,((IP-ASN,123),(IP-ASN,456))\nPROCESS-NAME,example\n"
                           "USER-AGENT,Test*\nURL-REGEX,^https://example.com/\n")
        sites, ips, stats = build.convert_category(path)
        self.assertEqual(sites, {"full:example.com", "domain:example.com", "keyword:.example-", "full:192.0.2.1"})
        self.assertEqual(ips, {"192.0.2.0/24", "2001:db8::/32"})
        self.assertEqual(stats["duplicates_removed"], 1)
        self.assertEqual(stats["by_rule_type"]["DOMAIN"], {"read": 3, "converted": 3, "skipped": 0})
        self.assertEqual(len(stats["skipped"]), 6)
        self.assertEqual(len(stats["warnings"]), 2)
        self.assertEqual(stats["skipped"][2]["line"], 12)
        self.assertEqual(stats["skipped"][2]["path"], str(path))
        self.assertEqual(stats["sha256"], build.sha256(path))

    def test_parse_rule_invalid_inputs_and_injection(self):
        for raw in ["IP-CIDR,192.0.2.1/24", "IP-CIDR6,192.0.2.0/24",
                    "IP-CIDR,2001:db8::/32", "IP-CIDR6,fe80::%eth0/64", "IP-CIDR,999.0.0.0/8", "IP-CIDR,192.0.2.0/24,resolve",
                    "IP-CIDR,192.0.2.0/24,no-resolve,extra", "IP-ASN,123,unknown", "DOMAIN,",
                    "DOMAIN,example.com,no-resolve", "DOMAIN", "UNKNOWN,example.com", "AND,",
                    "PROCESS-NAME,test,extra", "DOMAIN,example..com", "DOMAIN,-example.com",
                    "DOMAIN,example.com.", "DOMAIN," + "a" * 64 + ".com", "DOMAIN,例子.com",
                    "DOMAIN,include:other", "DOMAIN,example.com @ads", "DOMAIN,example.com &other",
                    "DOMAIN,example.com#comment", "DOMAIN,example.com\t@attr", "DOMAIN,example.com\x00",
                    "DOMAIN,example.com\ninclude:other", "DOMAIN-KEYWORD,word:include", "DOMAIN-KEYWORD,word @ads"]:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                build.parse_rule(raw)
        self.assertEqual(build.parse_rule("DOMAIN-KEYWORD,-partial.")[1], "keyword:-partial.")

    def test_parse_rule_single_ips_and_literal_underscore_keywords(self):
        self.assertEqual(build.parse_rule("IP-CIDR,192.0.2.1")[1], "192.0.2.1/32")
        self.assertEqual(build.parse_rule("IP-CIDR6,2001:4060:1:1005::10:32,no-resolve")[1],
                         "2001:4060:1:1005::10:32/128")
        for keyword in ("_vmind.qqvideo.tc.qq.com", "wb_ad"):
            self.assertEqual(build.parse_rule("DOMAIN-KEYWORD," + keyword)[1], "keyword:" + keyword)
        for raw in ("IP-CIDR,2001:db8::1", "IP-CIDR6,192.0.2.1", "IP-CIDR6,invalid",
                    "DOMAIN-SUFFIX,_example.com", "DOMAIN-KEYWORD,wb_ad @ads",
                    "DOMAIN-KEYWORD,wb_ad#comment", "DOMAIN-KEYWORD,wb_ad:include"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                build.parse_rule(raw)

    def test_parse_rule_mapped_ipv6_compiler_limit_is_narrow(self):
        for value in ("::ffff:113.248.172.245/128", "::ffff:71f8:acf5/128",
                      "0:0:0:0:0:ffff:71f8:acf5/128", "::ffff:0:0/96", "::ffff:192.0.2.0/120"):
            rule = build.parse_rule("IP-CIDR6," + value)
            self.assertIsNone(rule[1])
            self.assertIn("pinned GeoIP compiler", rule[3])
        for value in ("2001:db8::/32", "::fffe:0:0/95", "::/0", "::/80"):
            self.assertEqual(build.parse_rule("IP-CIDR6," + value)[1], value)
        for value in ("::ffff:192.0.2.1/120", "::ffff:0:0/95"):
            with self.assertRaises(ValueError):
                build.parse_rule("IP-CIDR6," + value)
        path = self.source("Mapped", "IP-CIDR6,::ffff:113.248.172.245/128,no-resolve\n")
        sites, ips, stats = build.convert_category(path, allow_empty=True)
        self.assertFalse(sites or ips)
        self.assertEqual(stats["skipped"][0]["line"], 1)
        self.assertEqual(stats["by_rule_type"]["IP-CIDR6"], {"read": 1, "converted": 0, "skipped": 1})

    def test_error_source_and_empty_category(self):
        path = self.source("Bad", "# header\nIP-CIDR,192.0.2.1/24\n")
        with self.assertRaisesRegex(ValueError, r"Bad.list:2:"):
            build.convert_category(path)
        for text in ("# only comment\n", "IP-ASN,123\n"):
            path.write_text(text)
            with self.assertRaisesRegex(ValueError, "no supported rules"):
                build.convert_category(path)

    def test_category_paths(self):
        self.source("Sample", "DOMAIN,example.com")
        self.assertEqual(build.category_paths(["Sample"], self.root)[0][0], "sample")
        for names in (["../Sample"], ["/Sample"], ["Sample", "sample"], ["Missing"], ["Sample", "Sample"]):
            with self.subTest(names=names), self.assertRaises(ValueError):
                build.category_paths(names, self.root)
        link = self.root / "rule/Surge/Escape"
        link.symlink_to(self.root)
        with self.assertRaises(ValueError):
            build.category_paths(["Escape"], self.root)

    def nested_source(self, relative, text="DOMAIN,example.com\n", all_only=False):
        directory = self.root / "rule/Surge" / relative
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (directory.name + ("_All" if all_only else "") + ".list")
        path.write_text(text)
        return path

    def test_category_paths_recursive_inventory_and_all_preference(self):
        self.source("Sample", "DOMAIN,main.example\n")
        preferred = self.nested_source("Sample", all_only=True)
        only_all = self.nested_source("OnlyAll", all_only=True)
        child = self.nested_source("Cloud/Child")
        variant = child.with_name("Child_Resolve.list")
        variant.write_text("DOMAIN,variant.example\n")
        inventory = []
        paths = dict(build.category_paths(root=self.root, inventory=inventory))
        self.assertEqual(paths, {"sample": preferred, "onlyall": only_all, "child": child})
        self.assertEqual(dict(build.category_paths(["Sample", "Child"], self.root)),
                         {"sample": preferred, "child": child})
        self.assertEqual(build.category_paths(["Cloud/Child"], self.root), [("child", child)])
        records = {r["directory"]: r for r in inventory}
        self.assertEqual(records["Cloud"]["status"], "container")
        self.assertEqual(records["Cloud/Child"]["other_list_files"], [str(variant)])
        self.assertEqual(len(records), 4)

    def test_category_paths_nested_collisions_and_apostrophes(self):
        for relative in ("Direct", "AdGuardSDNSFilter/Direct", "Game/Assassin'sCreed-Odyssey",
                         "Assassin'sCreed/Assassin'sCreed-Odyssey"):
            self.nested_source(relative)
        paths = dict(build.category_paths(root=self.root))
        self.assertEqual(set(paths), {"direct", "adguardsdnsfilter-direct", "game-assassinscreed-odyssey",
                                     "assassinscreed-assassinscreed-odyssey"})
        self.assertEqual(build.category_paths(["Direct"], self.root)[0][0], "direct")
        self.assertEqual(build.category_paths(["AdGuardSDNSFilter/Direct"], self.root)[0][0],
                         "adguardsdnsfilter-direct")
        for selection in (["Assassin'sCreed-Odyssey"], ["Game/Assassin'sCreed-Odyssey", "Game/Assassin'sCreed-Odyssey"]):
            with self.assertRaises(ValueError):
                build.category_paths(selection, self.root)
        self.nested_source("Game-AssassinsCreed-Odyssey")
        with self.assertRaisesRegex(ValueError, "collision"):
            build.category_paths(root=self.root)

    def test_category_paths_rejects_unaccounted_lists_and_unsafe_names(self):
        path = self.nested_source("Odd")
        path.rename(path.with_name("unrelated.list"))
        with self.assertRaisesRegex(ValueError, "no category"):
            build.category_paths(root=self.root)
        path.with_name("unrelated.list").rename(path)
        self.nested_source("Unsafe@name")
        with self.assertRaisesRegex(ValueError, "invalid category directory"):
            build.category_paths(root=self.root)

    def test_output_nonempty_refused_without_overwrite(self):
        directory = self.root / "out"
        build.prepare_output(directory)
        marker = directory / "keep"
        marker.write_text("unchanged")
        for path in (directory, marker):
            with self.assertRaises(ValueError):
                build.prepare_output(path)
        self.assertEqual(marker.read_text(), "unchanged")

    def test_readback_exact_types_and_aggregated_coverage(self):
        sites = {"sample": {"full:example.com", "domain:example.com", "keyword:example"}}
        ips = {"sample": {"192.0.2.0/25", "192.0.2.128/25", "2001:db8::/32"}}
        decoded = decoded_data(sites, {"sample": {"192.0.2.0/24", "2001:db8::/32"}})
        decoded["geosite"]["entry"][0]["domain"][-1].pop("type")  # protobuf omits default Plain
        self.assertEqual(build.verify_readback(decoded, sites, ips)["sample"]["geoip_ipv6"], 1)
        for mutation in ("domain", "extra_category", "cidr", "attribute", "reverse", "duplicate"):
            bad = copy.deepcopy(decoded)
            if mutation == "domain":
                bad["geosite"]["entry"][0]["domain"].pop()
            elif mutation == "extra_category":
                bad["geoip"]["entry"].append({"countryCode": "THIRDPARTY", "cidr": []})
            elif mutation == "cidr":
                bad["geoip"]["entry"][0]["cidr"][0]["prefix"] = 23
            elif mutation == "attribute":
                bad["geosite"]["entry"][0]["domain"][0]["attribute"] = [{"key": "ads"}]
            elif mutation == "reverse":
                bad["geoip"]["entry"][0]["reverseMatch"] = True
            else:
                bad["geosite"]["entry"].append(bad["geosite"]["entry"][0])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                build.verify_readback(bad, sites, ips)

    def test_profile_urls_references_and_roundtrip(self):
        profile = build.routing_profile(build.TEMPLATE_CATEGORIES, build.TEMPLATE_CATEGORIES, {"telegram"},
                                        "https://example.com/geosite.dat?a=1", "http://127.0.0.1:8080/geoip.dat")
        self.assertEqual(profile["ProxyIp"], ["geoip:telegram"])
        self.assertEqual(profile["BlockIp"], [])
        self.assertEqual(profile["BlockSites"], ["geosite:advertisinglite"])
        self.assertEqual(profile["ProxySites"], ["geosite:openai", "geosite:telegram"])
        self.assertEqual(profile["GlobalProxy"], "true")
        self.assertEqual(profile["FakeDNS"], "false")
        self.assertEqual(profile["DomainStrategy"], "AsIs")
        build.write_profile(self.root, profile)
        link = (self.root / "routing.txt").read_text().strip()
        self.assertTrue(link.startswith("happ://routing/add/"))
        self.assertEqual(base64.b64decode(link.removeprefix("happ://routing/add/"), validate=True),
                         (self.root / "routing.json").read_bytes())
        self.assertEqual(json.loads((self.root / "routing.json").read_bytes()), profile)
        with self.assertRaises(ValueError):
            build.routing_profile({"openai"}, {"openai"}, {}, "https://example.com/a", "https://example.com/b")
        for url in ("file:///tmp/a", "https:///a", "https://u:p@example.com/a", "https://u@example.com",
                    "https://example.com:bad/a", "https://example.com:70000/a", "http://bad host/a",
                    "https://example.com\n/a", "https://example.com/#a", "https://bad\\host/a", "https://%bad/a", "https://example.com/%ZZ", ""):
            with self.subTest(url=url), self.assertRaises(ValueError):
                build.validate_url(url)
        self.assertEqual(build.validate_url("http://[::1]:8080/a"), "http://[::1]:8080/a")

    def test_tools_missing_failed_and_wrong_version(self):
        with self.assertRaises(ValueError):
            build.tool_info(self.root / "missing", "geoip")
        with patch("build.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "unrecognized", "")):
            with self.assertRaisesRegex(ValueError, "expected clean pinned"):
                build.tool_info(Path(sys.executable), "geoip")
        commands = []
        with self.assertRaisesRegex(ValueError, "exited 7"):
            build.run_tool([sys.executable, "-c", "import sys; print('failure'); sys.exit(7)"], self.root, "failure", commands)
        self.assertEqual(commands[0]["returncode"], 7)
        self.assertIn("failure", (self.root / "failure.log").read_text())

    def args(self, names):
        return argparse.Namespace(categories=names, output=self.root / "out", geosite_url=None, geoip_url=None,
                                  geosite_tool=Path(sys.executable), geoip_tool=Path(sys.executable), geo_reader=Path(sys.executable))

    def test_single_sided_collections_fail_before_tools(self):
        for label, text in (("domain", "IP-CIDR,192.0.2.0/24"), ("CIDR", "DOMAIN,example.com")):
            self.source("Sample", text)
            with patch("build.category_paths", return_value=build.category_paths(["Sample"], self.root)), patch("build.tool_info") as info:
                with self.assertRaisesRegex(ValueError, "no " + label):
                    build.build(self.args(["Sample"]))
                info.assert_not_called()

    def test_build_mixed_single_sided_categories(self):
        self.source("Domains", "DOMAIN,example.com\n")
        self.source("IPs", "IP-CIDR,192.0.2.0/24\n")
        args = self.args(["Domains", "IPs"])
        decoded = decoded_data({"domains": {"full:example.com"}}, {"ips": {"192.0.2.0/24"}})

        def compiler(command, output, label, commands):
            if label == "readback":
                return json.dumps(decoded)
            (output / ("geosite.dat" if label == "geosite-build" else "geoip.dat")).write_bytes(b"mock")
            return ""

        with patch("build.category_paths", return_value=build.category_paths(args.categories, self.root)), \
                patch("build.tool_info", return_value={"path": sys.executable}), patch("build.run_tool", side_effect=compiler), redirect_stdout(io.StringIO()):
            build.build(args)
        report = json.loads((args.output / "conversion-report.json").read_text())
        self.assertEqual(report["status"], "validated")
        self.assertEqual(report["categories"]["domains"]["after_compile"]["geoip"], 0)
        self.assertFalse((args.output / "routing.json").exists())
        config = json.loads((args.output / "geoip-config.json").read_text())
        self.assertEqual([v["args"]["name"] for v in config["input"]], ["ips"])

    def test_build_all_skips_unsupported_categories_without_empty_entries(self):
        self.source("Supported", "DOMAIN,example.com\nIP-CIDR,192.0.2.1\n")
        self.source("ASN", "IP-ASN,123\n")
        self.source("Unsupported", "USER-AGENT,Example*\nPROCESS-NAME,example\n")
        self.source("Empty", "# no rules\n")
        paths = build.category_paths(root=self.root)
        args = self.args(None)
        decoded = decoded_data({"supported": {"full:example.com"}}, {"supported": {"192.0.2.1/32"}})

        def compiler(command, output, label, commands):
            if label == "readback":
                return json.dumps(decoded)
            (output / ("geosite.dat" if label == "geosite-build" else "geoip.dat")).write_bytes(b"mock")
            return ""

        with patch("build.category_paths", return_value=paths), patch("build.tool_info", return_value={"path": sys.executable}), \
                patch("build.run_tool", side_effect=compiler), redirect_stdout(io.StringIO()):
            build.build(args)
        report = json.loads((args.output / "conversion-report.json").read_text())
        self.assertEqual(report["summary"]["included_categories"], 1)
        self.assertEqual(report["summary"]["skipped_categories"], 3)
        self.assertEqual(report["categories"]["asn"]["status"], "skipped")
        self.assertEqual(report["categories"]["asn"]["skipped"][0]["line"], 1)
        self.assertNotIn("after_compile", report["categories"]["asn"])
        self.assertEqual([p.name for p in (args.output / "geosite-input").iterdir()], ["supported"])
        self.assertEqual([p.name for p in (args.output / "geoip-input").iterdir()], ["supported"])
        with self.assertRaisesRegex(ValueError, "no supported rules"):
            build.convert_category(self.root / "rule/Surge/ASN/ASN.list")
        with patch("build.build") as run:
            self.assertEqual(build.main(["--geosite-tool", "site", "--geoip-tool", "ip",
                                         "--geo-reader", "reader", "--output", "out"]), 0)
            self.assertIsNone(run.call_args.args[0].categories)

    def test_cli_errors_never_report_success(self):
        source = self.source("Sample", "DOMAIN,example.com\nIP-CIDR,192.0.2.0/24\n")
        argv = ["--categories", "Sample", "--geosite-tool", str(self.root / "missing"),
                "--geoip-tool", sys.executable, "--geo-reader", sys.executable, "--output", str(self.root / "out")]
        with patch("build.category_paths", return_value=[("sample", source)]), redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(build.main(argv), 1)
            self.assertEqual(build.main(argv + ["--geoip-url", "https://example.com/a"]), 1)
            with patch("build.tool_info", return_value={"path": sys.executable}):
                # Python rejects compiler flags, giving a real failed child process without Go.
                self.assertEqual(build.main(argv), 1)
            self.assertNotIn("Validated", stdout.getvalue())
        report = json.loads((self.root / "out/conversion-report.json").read_text())
        self.assertEqual(report["status"], "failed")
        self.assertNotEqual(report["commands"][0]["returncode"], 0)


if __name__ == "__main__":
    unittest.main()
