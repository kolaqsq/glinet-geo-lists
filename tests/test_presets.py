import ipaddress
import unittest

from helpers import FIXTURES

from glgeo.errors import BuildError
from glgeo.formats.rules import parse_rule
from glgeo.model import IpSet, fit_networks
from glgeo.presets import Context, build_preset, check_include

GEOSITE = {
    "a": [parse_rule("domain:a.ru"), parse_rule("domain:ads.a.ru:@ads"), parse_rule("full:www.a.ru")],
    "b": [parse_rule("domain:sub.a.ru"), parse_rule("domain:b.ru")],
}
GEOIP = {"ru": IpSet([ipaddress.ip_network("5.3.0.0/17"), ipaddress.ip_network("5.3.128.0/17")],
                     [ipaddress.ip_network("2a00::/16")])}


def build(*include, aggregate_ips=False, max_ips=55000):
    preset = {"include": list(include), "aggregate_ips": aggregate_ips}
    return build_preset("p", preset, Context(GEOSITE, GEOIP, False, FIXTURES, max_ips))


def nets(*texts):
    return [ipaddress.ip_network(t) for t in texts]


class PresetTest(unittest.TestCase):
    def test_merge_and_order(self):
        domains, v4, v6 = build("geosite:b", "geosite:a", "geoip:ru", "file:custom.txt")
        self.assertEqual(domains, ["a.ru", "b.ru", "gosuslugi.ru"])
        self.assertEqual(v4, ["5.3.0.0/16", "95.167.0.0/16"])
        self.assertEqual(v6, [])

    def test_attr_and_v6(self):
        domains, v4, v6 = build("geosite:a@ads", "geoip6:ru")
        self.assertEqual((domains, v4, v6), (["ads.a.ru"], [], ["2a00::/16"]))

    def test_unknown_list(self):
        with self.assertRaises(BuildError):
            build("geosite:missing")
        with self.assertRaises(BuildError):
            build("geoip:missing")

    def test_aggregate_ips(self):
        _, v4, _ = build("geoip:ru", "file:custom.txt", aggregate_ips=True, max_ips=1)
        self.assertEqual(v4, ["5.3.0.0/16", "95.167.0.0/16"])  # /16 is the widest allowed: budget not met
        _, v4, _ = build("geoip:ru", "file:custom.txt", aggregate_ips=False, max_ips=1)
        self.assertEqual(v4, ["5.3.0.0/16", "95.167.0.0/16"])

    def test_check_include(self):
        self.assertIsNone(check_include("geosite:geolocation-!cn@!cn", FIXTURES))
        self.assertIsNone(check_include("file:custom.txt", FIXTURES))
        self.assertIsNotNone(check_include("geosite:", FIXTURES))
        self.assertIsNotNone(check_include("geoip:Bad Name", FIXTURES))
        self.assertIsNotNone(check_include("asn:13238", FIXTURES))


if __name__ == "__main__":
    unittest.main()


class FitNetworksTest(unittest.TestCase):
    SAMPLE = ("10.0.0.1/32", "10.0.0.3/32", "10.0.1.0/32", "192.168.0.1/32")

    def test_within_budget_unchanged(self):
        self.assertEqual(fit_networks(nets("10.0.0.0/25", "10.0.0.128/25"), 1, 16), (nets("10.0.0.0/24"), 0))

    def test_cheapest_merge_first(self):
        self.assertEqual(fit_networks(nets(*self.SAMPLE), 3, 16),
                         (nets("10.0.0.0/30", "10.0.1.0/32", "192.168.0.1/32"), 2))
        self.assertEqual(fit_networks(nets(*self.SAMPLE), 2, 16), (nets("10.0.0.0/23", "192.168.0.1/32"), 509))

    def test_min_prefix_limits_widening(self):
        # one entry would need 0.0.0.0/0; beyond /16 nothing is merged, the best 2-entry result comes back
        self.assertEqual(fit_networks(nets(*self.SAMPLE), 1, 16), (nets("10.0.0.0/23", "192.168.0.1/32"), 509))

    def test_ipv6(self):
        fitted, extra = fit_networks(nets("2a00::1/128", "2a00::3/128", "2a01::/32"), 2, 32)
        self.assertEqual((fitted, extra), (nets("2a00::/126", "2a01::/32"), 2))
