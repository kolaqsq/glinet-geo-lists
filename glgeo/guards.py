"""Checks that fail the build: an empty or broken list on the router is worse than a stale one."""

import json
import re

from . import net
from .errors import BuildError


def check_min_lines(rel, count, min_lines):
    if count < min_lines:
        return [f"{rel}: {count} lines, expected at least {min_lines}"]
    return []


def router_limit_problems(lines, v4, v6, opts):
    """What GL.iNet would silently lose from a list with this many lines and networks.
    It reads only the first router_max_lines lines, and IPv4/IPv6 networks go into ipsets of
    65536 entries each, shared with the IPs of resolved domains (router_max_ips leaves room for them)."""
    problems = []
    if lines > opts["router_max_lines"]:
        problems.append(f"{lines} lines, the router reads only the first {opts['router_max_lines']}")
    for family, count in (("IPv4", v4), ("IPv6", v6)):
        if count > opts["router_max_ips"]:
            problems.append(f"{count} {family} networks, more than router_max_ips={opts['router_max_ips']}")
    return problems


def load_previous_index(ref, report):
    """Returns index.json of the previous build ({"generated", "files"}) or None."""
    if not ref:
        return None
    try:
        if re.match(r"^https?://", ref):
            previous = json.loads(net.http_get(ref))
        else:
            with open(ref, encoding="utf-8") as f:
                previous = json.load(f)
        if not (isinstance(previous, dict) and isinstance(previous.get("files"), dict)):
            raise ValueError("no files in it")
        return previous
    except (BuildError, OSError, ValueError) as e:
        report.warn(f"previous index unavailable ({e}), shrink guard skipped")
        return None


def check_shrink(index, previous, max_shrink, min_prev, report):
    errors = []
    for rel, old in sorted(previous.items()):
        new = index.get(rel)
        if new is None:
            report.warn(f"{rel} disappeared (had {old} lines)")
        elif old >= min_prev and new < old * (1 - max_shrink):
            errors.append(f"{rel}: {old} -> {new} lines")
    return errors
