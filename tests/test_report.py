import contextlib
import io
import os
import tempfile
import unittest
from unittest import mock

import helpers  # noqa: F401

from glgeo.__main__ import main
from glgeo.report import Report


class ReportTest(unittest.TestCase):
    def test_annotations_only_in_actions(self):
        report = Report()
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            report.warn("quiet")
            with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
                report.error("100% broken\nsecond line")
        self.assertEqual(out.getvalue(), "::error::100%25 broken%0Asecond line\n")

    def test_failed_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = os.path.join(tmp, "summary.md")
            with contextlib.redirect_stderr(io.StringIO()):
                code = main(["--config", os.path.join(tmp, "missing.json"), "--out", tmp, "--summary", summary])
            self.assertEqual(code, 1)
            with open(summary) as f:
                text = f.read()
        self.assertIn("**Failed: nothing is published", text)
        self.assertIn("### Errors\n\n- ", text)


if __name__ == "__main__":
    unittest.main()
