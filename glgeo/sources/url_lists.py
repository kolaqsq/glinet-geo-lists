"""Lists from plain-text files at any URL, named in the config; one list may join several files."""

import re

from .. import net
from ..config import REQUIRED
from ..formats.hosts import parse_hosts_file
from ..formats.iplist import parse_ip_file
from ..formats.rules import parse_rule_file
from ..log import log
from ..model import IpSet

KINDS = ("geosite", "geoip")
KEYS = {"lists": (dict, REQUIRED), "format": (str, "rules")}
FORMATS = {"rules": parse_rule_file, "hosts": parse_hosts_file}
URL_RE = re.compile(r"^https?://\S+$")


def check(src):
    from . import NAME_RE

    errors = []
    if src.get("format") not in FORMATS:
        errors.append(f"format: expected one of {', '.join(FORMATS)}, got {src.get('format')!r}")
    for name, urls in src.get("lists", {}).items():
        if not NAME_RE.match(name):
            errors.append(f"lists.{name}: name must match {NAME_RE.pattern}")
        if not (isinstance(urls, list) and urls and all(isinstance(u, str) and URL_RE.match(u) for u in urls)):
            errors.append(f"lists.{name}: expected a non-empty array of http(s) URLs")
    return errors


def load(src, kind, wanted):
    lists = {name: urls for name, urls in src["lists"].items() if wanted(name)}
    texts = net.download_all(sorted({u for urls in lists.values() for u in urls}))
    if kind == "geosite":
        parse = FORMATS[src["format"]]
        return {name: [r for u in urls for r in parse(texts[u])] for name, urls in lists.items()}
    result = {}
    for name, urls in lists.items():
        v4, v6, bad = parse_ip_file("\n".join(texts[u] for u in urls))
        if bad:
            log(f"geoip {name}: {bad} invalid lines skipped")
        result[name] = IpSet(v4, v6)
    return result


def updated(src):
    return [(u, net.last_modified(u)) for u in sorted({u for urls in src["lists"].values() for u in urls})]
