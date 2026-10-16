import ipaddress
import unittest

import helpers  # noqa: F401

from glgeo.formats.rules import parse_rule
from glgeo.model import DomainSet, IpSet, norm_domain


def rules(*lines):
    return [parse_rule(line) for line in lines]


class DomainSetTest(unittest.TestCase):
    def test_compact_under_wildcard_only(self):
        ds = DomainSet()
        ds.add_rules(rules("domain:example.com", "full:www.example.com", "full:other.org", "domain:a.other.org"), None, False)
        self.assertEqual(ds.compact(), ["a.other.org", "example.com", "other.org"])

    def test_drops(self):
        ds = DomainSet()
        ds.add_rules(rules("domain:youtube", "keyword:abc", "regexp:x", "domain:\"bad.ru", "domain:OK.RU."), None, False)
        self.assertEqual(ds.compact(), ["ok.ru"])
        self.assertEqual(ds.dropped, {"tld": 1, "keyword": 1, "regexp": 1, "invalid": 1})

    def test_allow_tld(self):
        ds = DomainSet()
        ds.add_rules(rules("domain:ru", "domain:ya.ru"), None, True)
        self.assertEqual(ds.compact(), ["ru"])

    def test_attr_filter(self):
        rs = rules("domain:a.cn:@cn", "domain:b.com")
        for flt, want in (("cn", ["a.cn"]), ("!cn", ["b.com"]), ("", ["a.cn", "b.com"])):
            ds = DomainSet()
            ds.add_rules(rs, flt, False)
            self.assertEqual(ds.compact(), want)


class NormDomainTest(unittest.TestCase):
    def test_idn(self):
        self.assertEqual(norm_domain("госуслуги.рф"), "xn--c1aapkosapc.xn--p1ai")

    def test_underscore_rejected(self):
        # GL.iNet refuses such lines ("Invalid Line Number")
        self.assertIsNone(norm_domain("_dmarc.angus.su"))
        self.assertIsNone(norm_domain("a_b.example.com"))
        self.assertEqual(norm_domain("a-b.example.com"), "a-b.example.com")


class IpSetTest(unittest.TestCase):
    def test_collapse_per_family(self):
        nets = [ipaddress.ip_network(n) for n in ("10.0.0.0/25", "10.0.0.128/25", "2a00::/16")]
        ips = IpSet([n for n in nets if n.version == 4], [n for n in nets if n.version == 6])
        ips.update(IpSet(v4=[ipaddress.ip_network("10.0.1.0/24")]))
        self.assertEqual(ips.compact4(), ["10.0.0.0/23"])
        self.assertEqual(ips.compact6(), ["2a00::/16"])


if __name__ == "__main__":
    unittest.main()
