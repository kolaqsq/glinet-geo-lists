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
        run(os.path.join(FIXTURES, "config.json"), self.out, cache_dir=self.cache)
        with open(os.path.join(self.out, "index.json")) as f:
            index = json.load(f)["files"]
        self.assertEqual(index, {
            "geosite/category-ru.txt": 1, "geosite/extra.txt": 2, "geosite/dat-only.txt": 1,
            "geoip/ru.txt": 1, "geoip6/ru.txt": 1, "geoip/private.txt": 1,
            "presets/ru-direct.txt": 5, "presets/v6.txt": 1,
        })
        self.assertEqual(self.read("geosite/category-ru.txt"), ["yandex.ru"])
        self.assertEqual(self.read("geosite/extra.txt"), ["ads.example.ru", "from-yml.ru"])
        self.assertEqual(self.read("presets/ru-direct.txt"),
                         ["from-yml.ru", "gosuslugi.ru", "yandex.ru", "5.3.0.0/16", "95.167.0.0/16"])
        self.assertEqual(self.read("presets/v6.txt"), ["2a00:1148::/32"])

    def test_router_limit_fails_but_writes(self):
        with self.assertRaises(BuildError) as cm:
            run(self.config(router_max_ips=1), self.out, cache_dir=self.cache)
        self.assertIn("presets/ru-direct.txt: 2 IPv4 networks", str(cm.exception))
        self.assertTrue(os.path.exists(os.path.join(self.out, "index.json")))

    def test_shrink_guard(self):
        previous = os.path.join(self.tmp, "previous.json")
        with open(previous, "w") as f:
            json.dump({"files": {"presets/ru-direct.txt": 100}}, f)
        with self.assertRaises(BuildError) as cm:
            run(self.config(shrink_min_lines=10), self.out, previous_index=previous, cache_dir=self.cache)
        self.assertIn("presets/ru-direct.txt: 100 -> 5 lines", str(cm.exception))

    def test_bad_checksum(self):
        with open(net.cache_path(self.cache, "https://example.test/geosite.dat.sha256sum"), "w") as f:
            f.write("0" * 64)
        with self.assertRaises(BuildError):
            run(os.path.join(FIXTURES, "config.json"), self.out, cache_dir=self.cache)


if __name__ == "__main__":
    unittest.main()
