import unittest

from helpers import pb

from glgeo.errors import BuildError
from glgeo.formats.geosite_dat import parse_geosite_dat
from glgeo.formats.hosts import parse_hosts_file
from glgeo.formats.iplist import parse_ip_file
from glgeo.formats.plain_yml import parse_plain_yml
from glgeo.formats.rules import parse_rule


class ParseRuleTest(unittest.TestCase):
    def test_kinds_and_attrs(self):
        self.assertEqual(parse_rule("domain:acer.com.cn:@cn"), ("domain", "acer.com.cn", frozenset({"cn"})))
        self.assertEqual(parse_rule("full:a.b.com"), ("full", "a.b.com", frozenset()))
        self.assertEqual(parse_rule("example.com # note"), ("domain", "example.com", frozenset()))
        self.assertIsNone(parse_rule("# comment"))


class PlainYmlTest(unittest.TestCase):
    def test_length_mismatch(self):
        text = 'lists:\n  - name: "x"\n    length: 2\n    rules:\n      - "domain:a.com"\n'
        with self.assertRaises(BuildError):
            parse_plain_yml(text)

    def test_parse(self):
        text = 'lists:\n  - name: "X"\n    length: 2\n    rules:\n      - "domain:a.com"\n      - "regexp:^a$"\n'
        self.assertEqual(parse_plain_yml(text), {"x": [("domain", "a.com", frozenset()), ("regexp", "^a$", frozenset())]})


class GeositeDatTest(unittest.TestCase):
    def test_parse(self):
        dom1 = pb(1, 2) + pb(2, b"example.ru") + pb(3, pb(1, b"CN") + pb(2, 1))
        dom2 = pb(1, 3) + pb(2, b"www.x.ru")
        dom3 = pb(2, b"kw")  # type omitted = 0 = keyword
        site = pb(1, b"RU-TEST") + pb(2, dom1) + pb(2, dom2) + pb(2, dom3)
        data = pb(1, site) + pb(1, pb(1, b"EMPTY"))
        self.assertEqual(parse_geosite_dat(data), {
            "ru-test": [("domain", "example.ru", frozenset({"cn"})), ("full", "www.x.ru", frozenset()),
                        ("keyword", "kw", frozenset())],
            "empty": [],
        })

    def test_truncated(self):
        data = pb(1, pb(1, b"RU") + pb(2, pb(2, b"example.ru")))
        with self.assertRaises(BuildError):
            parse_geosite_dat(data[:-3])
        with self.assertRaises(BuildError):
            parse_geosite_dat(data + b"\x0a")


class IpListTest(unittest.TestCase):
    def test_parse(self):
        v4, v6, bad = parse_ip_file("# c\n10.0.0.0/25\n10.0.0.1/25\n2a00::/16\nbad\n")
        self.assertEqual([str(n) for n in v4], ["10.0.0.0/25", "10.0.0.0/25"])
        self.assertEqual([str(n) for n in v6], ["2a00::/16"])
        self.assertEqual(bad, 1)


class HostsTest(unittest.TestCase):
    def test_parse(self):
        text = "### header\n0.0.0.0 a.example.com b.example.com # c\n127.0.0.1\nnot-an-ip x.com\n::1 v6.example.com\n"
        self.assertEqual([v for _, v, _ in parse_hosts_file(text)], ["a.example.com", "b.example.com", "v6.example.com"])
        self.assertEqual({k for k, _, _ in parse_hosts_file(text)}, {"domain"})


if __name__ == "__main__":
    unittest.main()
