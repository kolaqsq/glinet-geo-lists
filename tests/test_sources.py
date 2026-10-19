import datetime
import unittest

import helpers  # noqa: F401

from glgeo import sources
from glgeo.report import Report

NOW = datetime.datetime(2026, 10, 17, tzinfo=datetime.timezone.utc)


class FakeType:
    """A source type with fixed lists and update times."""
    KINDS = ("geosite",)

    def __init__(self, lists, updated):
        self.lists, self._updated = lists, updated

    def load(self, src, kind, wanted):
        return self.lists

    def updated(self, src):
        if isinstance(self._updated, Exception):
            raise self._updated
        return self._updated


def src(name, max_age_days=7):
    return {"name": name, "type": name, "min_lists": 1, "max_age_days": max_age_days}


class LoadAllTest(unittest.TestCase):
    def setUp(self):
        self.saved = dict(sources.REGISTRY)

    def tearDown(self):
        sources.REGISTRY.clear()
        sources.REGISTRY.update(self.saved)

    def load(self, *types):
        report = Report()
        for name, mod in types:
            sources.REGISTRY[name] = mod
        result = sources.load_all("geosite", [src(name, getattr(mod, "max_age", 7)) for name, mod in types], report, NOW)
        return result, report

    def test_stale_source_warns_but_loads(self):
        old = datetime.datetime(2026, 8, 10, tzinfo=datetime.timezone.utc)
        fresh = datetime.datetime(2026, 10, 16, 3, 0)  # naive means UTC
        result, report = self.load(("a", FakeType({"x": []}, [("a.dat", old), ("a.sum", fresh), ("a.txt", None)])))
        self.assertEqual(list(result), ["x"])
        self.assertEqual(report.warnings, ["geosite a: a.dat last updated 2026-08-10, 68 days ago (max_age_days=7)"])
        self.assertEqual(report.notes, ["geosite a: update time of a.txt unknown"])
        self.assertEqual(report.sources[0][3][1][1].tzinfo, datetime.timezone.utc)

    def test_age_check_off_and_failing(self):
        off = FakeType({"x": []}, [("a.dat", datetime.datetime(2020, 1, 1))])
        off.max_age = 0
        broken = FakeType({"y": []}, ValueError("rate limit"))
        _, report = self.load(("off", off), ("broken", broken))
        self.assertEqual(report.warnings, [])
        self.assertEqual(report.notes, ["geosite broken: cannot tell when it was last updated (rate limit)"])
        self.assertIsNone(report.sources[0][3])


class ResolveIncludesTest(unittest.TestCase):
    def test_nested_unknown_and_cycle(self):
        lists = {
            "a": [("domain", "a.ru", frozenset()), ("include", "B", frozenset())],
            "b": [("include", "c", frozenset()), ("include", "nope", frozenset())],
            "c": [("domain", "c.ru", frozenset()), ("include", "a", frozenset())],
        }
        report = Report()
        sources.resolve_includes(lists, report)
        self.assertEqual([v for _, v, _ in lists["a"]], ["a.ru", "c.ru"])
        self.assertEqual([v for _, v, _ in lists["c"]], ["c.ru"])  # a cycle is an upstream bug: that include is dropped
        self.assertEqual(len(report.notes), 2)


if __name__ == "__main__":
    unittest.main()
