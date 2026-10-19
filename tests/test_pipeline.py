"""The whole build on small local samples: downloads are served from a pre-filled --cache-dir."""

import hashlib
import json
import os
import shutil
import tempfile
import unittest

from helpers import FIXTURES, pb

from glgeo import net
from glgeo.errors import BuildError
from glgeo.pipeline import run
from glgeo.report import Report


def geosite_dat():
    def site(name, *domains):
        return pb(1, pb(1, name) + b"".join(pb(2, pb(1, 2) + pb(2, d)) for d in domains))
    # "extra" is also in dlc.yml, which comes first in the config and wins
    return site(b"EXTRA", b"from-dat.ru") + site(b"DAT-ONLY", b"dat.ru")


def fill_cache(cache):
    def put(url, data):
        os.makedirs(cache, exist_ok=True)
        with open(net.cache_path(cache, url), "wb") as f:
            f.write(data if isinstance(data, bytes) else data.encode())

    with open(os.path.join(FIXTURES, "dlc.yml"), "rb") as f:
        put("https://example.test/dlc.yml", f.read())
    dat = geosite_dat()
    put("https://example.test/geosite.dat", dat)
    put("https://example.test/geosite.dat.sha256sum", hashlib.sha256(dat).hexdigest() + "  geosite.dat\n")
    listing = []
    for name in sorted(os.listdir(os.path.join(FIXTURES, "geoip"))):
        url = f"https://example.test/geoip/{name}"
        listing.append({"name": name, "type": "file", "download_url": url})
        with open(os.path.join(FIXTURES, "geoip", name), "rb") as f:
            put(url, f.read())
    listing.append({"name": "text", "type": "dir", "download_url": None})
    put("https://api.github.com/repos/test/geoip/contents/text?ref=release", json.dumps(listing))
    put("https://api.github.com/repos/test/geoip/commits?sha=release&per_page=1&path=text",
        json.dumps([{"commit": {"committer": {"date": "2026-10-01T02:00:00Z"}}}]))
    put("https://example.test/a.lst", "a.example.ru\n# comment\n")
    put("https://example.test/b.lst", "b.example.ru\nsub.a.example.ru\n")
    put("https://example.test/include.lst", "include:category-ru\ninclude:missing\n")
    with open(net.cache_path(cache, "https://example.test/dlc.yml") + ".last-modified", "w") as f:
        f.write("Thu, 15 Oct 2026 07:45:34 GMT")


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cache = os.path.join(self.tmp, "cache")
        self.out = os.path.join(self.tmp, "out")
        fill_cache(self.cache)

    def tearDown(self):
        net.set_cache_dir(None)
        shutil.rmtree(self.tmp)

    def read(self, rel):
        with open(os.path.join(self.out, rel), encoding="utf-8") as f:
            return f.read().splitlines()

    def config(self, **options):
        """A copy of the fixture config with changed options, next to a copy of custom.txt."""
        with open(os.path.join(FIXTURES, "config.json")) as f:
            cfg = json.load(f)
        cfg["options"].update(options)
        shutil.copy(os.path.join(FIXTURES, "custom.txt"), self.tmp)
        path = os.path.join(self.tmp, "config.json")
        with open(path, "w") as f:
            json.dump(cfg, f)
        return path

    def test_build(self):
        report = Report()
        run(os.path.join(FIXTURES, "config.json"), self.out, cache_dir=self.cache, report=report)
        with open(os.path.join(self.out, "index.json")) as f:
            index = json.load(f)["files"]
        self.assertEqual(index, {
            "geosite/category-ru.txt": 1, "geosite/extra.txt": 2, "geosite/dat-only.txt": 1,
            "geosite/joined.txt": 2, "geosite/with-include.txt": 3,
            "geoip/ru.txt": 1, "geoip6/ru.txt": 1, "geoip/private.txt": 1,
            "presets/ru-direct.txt": 5, "presets/v6.txt": 1,
        })
        self.assertEqual(self.read("geosite/category-ru.txt"), ["yandex.ru"])
        self.assertEqual(self.read("geosite/extra.txt"), ["ads.example.ru", "from-yml.ru"])
        self.assertEqual(self.read("presets/ru-direct.txt"),
                         ["from-yml.ru", "gosuslugi.ru", "yandex.ru", "5.3.0.0/16", "95.167.0.0/16"])
        self.assertEqual(self.read("presets/v6.txt"), ["2a00:1148::/32"])
        self.assertEqual(self.read("geosite/joined.txt"), ["a.example.ru", "b.example.ru"])
        self.assertEqual(self.read("geosite/with-include.txt"), ["b.example.ru", "sub.a.example.ru", "yandex.ru"])

        updated = {name: dates for _, name, _, dates in report.sources}
        self.assertEqual(str(updated["yml"][0][1]), "2026-10-15 07:45:34+00:00")
        self.assertEqual(str(updated["dir"][0][1]), "2026-10-01 02:00:00+00:00")
        self.assertTrue(any("include:missing not resolved" in n for n in report.notes))
        summary = report.markdown()
        self.assertIn("**Passed: 10 lists.**", summary)
        self.assertIn("| `ru-direct` | 5 | — | 3 | 2 | 0 |", summary)
        self.assertIn("| geosite `yml` | 2 | 2026-10-15 07:45 UTC |", summary)

    def test_router_limit_fails_but_writes(self):
        with self.assertRaises(BuildError) as cm:
            run(self.config(router_max_ips=1), self.out, cache_dir=self.cache)
        self.assertIn("presets/ru-direct.txt: 2 IPv4 networks", str(cm.exception))
        self.assertTrue(os.path.exists(os.path.join(self.out, "index.json")))

    def test_shrink_guard(self):
        previous = os.path.join(self.tmp, "previous.json")
        with open(previous, "w") as f:
            json.dump({"files": {"presets/ru-direct.txt": 100}}, f)
        report = Report()
        with self.assertRaises(BuildError) as cm:
            run(self.config(shrink_min_lines=10), self.out, previous_index=previous, cache_dir=self.cache, report=report)
        self.assertIn("presets/ru-direct.txt: 100 -> 5 lines", str(cm.exception))
        self.assertEqual(report.changes, (1, 9, 0, "unknown"))
        self.assertIn("| `ru-direct` | 5 | 100 |", report.markdown())

    def test_bad_checksum(self):
        with open(net.cache_path(self.cache, "https://example.test/geosite.dat.sha256sum"), "w") as f:
            f.write("0" * 64)
        with self.assertRaises(BuildError):
            run(os.path.join(FIXTURES, "config.json"), self.out, cache_dir=self.cache)


if __name__ == "__main__":
    unittest.main()
