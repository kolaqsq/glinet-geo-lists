import json
import os
import tempfile
import unittest

from helpers import FIXTURES

from glgeo import config
from glgeo.errors import BuildError


def errors_for(raw, base_dir=FIXTURES):
    errors = []
    config.validate(raw, base_dir, errors)
    return errors


SOURCES = {"geosite": [{"name": "v2fly", "type": "v2fly-plain-yml", "url": "https://x"}], "geoip": []}


class ConfigTest(unittest.TestCase):
    def test_fixture_is_valid_and_defaults_filled(self):
        cfg = config.load(os.path.join(FIXTURES, "config.json"))
        self.assertEqual(cfg["options"]["max_shrink"], 0.5)
        self.assertEqual(cfg["options"]["router_max_ips"], 10)
        self.assertEqual(cfg["sources"]["geoip"][0]["ext"], ".txt")
        self.assertEqual(cfg["sources"]["geosite"][1]["min_lists"], 1)
        self.assertEqual(cfg["presets"]["v6"]["min_lines"], 1)
        self.assertEqual(cfg["sources"]["geosite"][0]["max_age_days"], 7)
        self.assertEqual(cfg["sources"]["geosite"][2]["format"], "rules")

    def test_url_lists(self):
        raw = {"sources": {"geosite": [
            {"name": "a", "type": "url-lists", "format": "csv", "lists": {"Bad": ["https://x/a"], "ok": "https://x/b", "e": []}},
        ]}}
        self.assertEqual(errors_for(raw), [
            "sources.geosite[0].format: expected one of rules, hosts, got 'csv'",
            "sources.geosite[0].lists.Bad: name must match ^[a-z0-9][a-z0-9!@._-]*$",
            "sources.geosite[0].lists.ok: expected a non-empty array of http(s) URLs",
            "sources.geosite[0].lists.e: expected a non-empty array of http(s) URLs",
        ])

    def test_unknown_key_is_an_error(self):
        raw = {"sources": SOURCES, "presets": {"p": {"include": ["geoip:ru"], "min_line": 5}}}
        self.assertEqual(len(errors_for(raw)), 1)
        self.assertIn("presets.p.min_line: unknown key", errors_for(raw)[0])

    def test_types(self):
        raw = {"options": {"allow_tld": "yes", "max_shrink": True}, "sources": SOURCES}
        self.assertEqual(errors_for(raw), [
            'options.allow_tld: expected true/false, got "yes"',
            "options.max_shrink: expected a number, got true",
        ])

    def test_source_type_and_keys(self):
        raw = {"sources": {"geoip": [{"name": "a", "type": "v2ray-dat", "url": "x"},
                                     {"name": "b", "type": "github-dir", "repo": "o/r"}]}}
        errors = errors_for(raw)
        self.assertIn("sources.geoip[0].type: 'v2ray-dat' cannot be used for geoip", errors)
        self.assertIn("sources.geoip[1].ref: required", errors)

    def test_includes(self):
        raw = {"sources": SOURCES, "presets": {"p": {"include": ["geosite:a@!", "bad", "file:nope.txt", "geoip6:ru"]}}}
        errors = errors_for(raw)
        self.assertEqual(len(errors), 3)
        self.assertTrue(all(e.startswith("presets.p.include[") for e in errors))

    def test_load_reports_all_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            with open(path, "w") as f:
                json.dump({"sources": {}, "extra": 1, "presets": {"P": {"include": []}}}, f)
            with self.assertRaises(BuildError) as cm:
                config.load(path)
            self.assertEqual(str(cm.exception).count("\n  "), 3)


if __name__ == "__main__":
    unittest.main()
