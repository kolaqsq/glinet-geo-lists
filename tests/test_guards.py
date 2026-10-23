import unittest

import helpers  # noqa: F401

from glgeo import guards
from glgeo.report import Report

OPTS = {"router_max_lines": 200000, "router_max_ips": 55000}


class GuardsTest(unittest.TestCase):
    def test_shrink_preset_fails_single_list_warns(self):
        previous = {"presets/a.txt": 100, "presets/b.txt": 100, "geoip6/kw.txt": 499, "geoip6/ru.txt": 1000, "geoip/x.txt": 5}
        index = {"presets/a.txt": 40, "presets/b.txt": 90, "geoip6/kw.txt": 127, "geoip6/ru.txt": 1000}
        report = Report()
        errors = guards.check_shrink(index, previous, 0.5, 100, report)
        self.assertEqual(errors, ["presets/a.txt: 100 -> 40 lines"])
        self.assertEqual(report.warnings, ["geoip/x.txt disappeared (had 5 lines)", "geoip6/kw.txt shrank: 499 -> 127 lines"])

    def test_shrink_of_a_whole_directory_fails(self):
        previous = {"geosite/a.txt": 600, "geosite/b.txt": 400, "geosite/c.txt": 50}
        index = {"geosite/a.txt": 200, "geosite/b.txt": 200, "geosite/c.txt": 50}
        errors = guards.check_shrink(index, previous, 0.5, 100, Report())
        self.assertEqual(errors, ["geosite/: 1050 -> 450 lines in total"])

    def test_min_lines(self):
        self.assertEqual(guards.check_min_lines("p.txt", 5, 5), [])
        self.assertEqual(guards.check_min_lines("p.txt", 4, 5), ["p.txt: 4 lines, expected at least 5"])

    def test_router_limits(self):
        self.assertEqual(guards.router_limit_problems(200000, 55000, 55000, OPTS), [])
        problems = guards.router_limit_problems(200001, 55001, 0, OPTS)
        self.assertEqual(len(problems), 2)
        self.assertIn("first 200000", problems[0])
        self.assertIn("IPv4", problems[1])


if __name__ == "__main__":
    unittest.main()
