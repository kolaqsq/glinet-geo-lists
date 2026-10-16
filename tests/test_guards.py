import unittest

import helpers  # noqa: F401

from glgeo import guards

OPTS = {"router_max_lines": 200000, "router_max_ips": 55000}


class GuardsTest(unittest.TestCase):
    def test_shrink(self):
        errors = guards.check_shrink({"a.txt": 40, "b.txt": 90}, {"a.txt": 100, "b.txt": 100, "c.txt": 5}, 0.5, 100)
        self.assertEqual(errors, ["a.txt: 100 -> 40 lines"])

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
