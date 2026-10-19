"""What a build did, for the log and for the GitHub Actions run page.

warn() and error() also print GitHub workflow commands when running in Actions, so they show up
as annotations on the run. markdown() is the job summary (--summary $GITHUB_STEP_SUMMARY)."""

import os

from .log import log


class Report:
    def __init__(self):
        self.sources = []  # (kind, name, lists added, [(what, datetime or None)] or None if not checked)
        self.presets = []  # (name, lines, domains, IPv4, IPv6, previous lines or None)
        self.lists = 0
        self.changes = None  # (lists whose line count changed, added, removed, previous generated)
        self.warnings = []
        self.notes = []
        self.errors = []

    def warn(self, msg):
        log(f"WARNING: {msg}")
        self.warnings.append(msg)
        _annotate("warning", msg)

    def note(self, msg):
        log(f"NOTE: {msg}")
        self.notes.append(msg)

    def error(self, msg):
        log(f"ERROR: {msg}")
        self.errors.append(msg)
        _annotate("error", msg)

    def markdown(self):
        out = ["## glinet-geo-lists build", ""]
        if self.errors:
            out.append("**Failed: nothing is published, the `release` branch keeps the previous build.**")
        else:
            out.append(f"**Passed: {self.lists} lists.**")
        if self.changes:
            changed, added, removed, generated = self.changes
            out.append("")
            out.append(f"Since the previous build ({generated}): line count changed in {changed} lists, "
                       f"{added} added, {removed} removed.")
        if self.presets:
            out += ["", "### Presets", "", "| Preset | Lines | Previous | Domains | IPv4 | IPv6 |", "|---|--:|--:|--:|--:|--:|"]
            for name, lines, domains, v4, v6, prev in self.presets:
                out.append(f"| `{name}` | {lines} | {'—' if prev is None else prev} | {domains} | {v4} | {v6} |")
        if self.sources:
            out += ["", "### Sources", "", "| Source | Lists | Last updated |", "|---|--:|---|"]
            for kind, name, added, updated in self.sources:
                out.append(f"| {kind} `{name}` | {added} | {_oldest(updated)} |")
        for title, items in (("Errors", self.errors), ("Warnings", self.warnings), ("Notes", self.notes)):
            if items:
                out += ["", f"### {title}", ""] + [_bullet(m) for m in items]
        return "\n".join(out) + "\n"

    def write_summary(self, path):
        with open(path, "a", encoding="utf-8") as f:
            f.write(self.markdown())


def _oldest(updated):
    """A source of several files is as fresh as its oldest file."""
    if updated is None:
        return "not checked"
    dates = [d for _, d in updated if d]
    return min(dates).strftime("%Y-%m-%d %H:%M UTC") if dates else "unknown"


def _bullet(msg):
    first, *rest = msg.split("\n")
    return "\n".join([f"- {first}"] + [f"  {line.strip()}" for line in rest])


def _annotate(level, msg):
    if os.environ.get("GITHUB_ACTIONS") == "true":
        text = msg.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::{level}::{text}", flush=True)
