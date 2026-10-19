"""Source types. Each module provides:

  KINDS  list kinds it can feed: "geosite" (data = list of rules) and/or "geoip" (data = IpSet)
  KEYS   its config keys: {key: (type, default)}, default REQUIRED for mandatory keys
  load(src, kind, wanted) -> {name: data}
         wanted(name) tells whether a list would be used; skip downloading the others
  updated(src) -> [(what, datetime or None)]
         when the upstream data last changed, called after load(); used by max_age_days
  check(src) -> [error]  optional, extra config checks beyond KEYS

A new type is a new module plus a line in REGISTRY.
"""

import datetime
import re

from ..errors import BuildError
from ..log import log
from . import github_dir, url_lists, v2fly_plain_yml, v2ray_dat

REGISTRY = {
    "v2fly-plain-yml": v2fly_plain_yml,
    "v2ray-dat": v2ray_dat,
    "github-dir": github_dir,
    "url-lists": url_lists,
}

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9!@._-]*$")


def load_all(kind, sources, report, now=None):
    """Returns {name: data}; an earlier source wins on name collisions."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    result = {}

    def wanted(name):
        return name not in result and bool(NAME_RE.match(name))

    for src in sources:
        mod = REGISTRY[src["type"]]
        lists = mod.load(src, kind, wanted)
        added = 0
        for name, data in lists.items():
            if wanted(name):
                result[name] = data
                added += 1
        log(f"{kind} {src['name']}: {len(lists)} lists, {added} added")
        if added < src["min_lists"]:
            raise BuildError(f"{kind} {src['name']}: only {added} lists added, expected at least {src['min_lists']}")
        report.sources.append((kind, src["name"], added, check_age(kind, src, mod, report, now)))
    return result


def check_age(kind, src, mod, report, now):
    """Warn about upstream data older than max_age_days (0 = don't check). Stale data is still
    published: failing would stop the updates of every other list too."""
    if not src["max_age_days"]:
        return None
    try:
        updated = [(what, _utc(when)) for what, when in mod.updated(src)]
    except (BuildError, ValueError, KeyError, IndexError, TypeError) as e:
        report.note(f"{kind} {src['name']}: cannot tell when it was last updated ({e})")
        return []
    for what, when in updated:
        if when is None:
            report.note(f"{kind} {src['name']}: update time of {what} unknown")
        elif (now - when).days > src["max_age_days"]:
            report.warn(f"{kind} {src['name']}: {what} last updated {when:%Y-%m-%d}, "
                        f"{(now - when).days} days ago (max_age_days={src['max_age_days']})")
    return updated


def _utc(when):
    if when is None:
        return None
    return when.replace(tzinfo=datetime.timezone.utc) if when.tzinfo is None else when.astimezone(datetime.timezone.utc)


def resolve_includes(lists, report):
    """Replace v2fly 'include:<name>' rules with the rules of that list, from any source.
    dlc.dat_plain.yml has them resolved already; plain-text sources may not."""
    done = {}

    def expand(name, stack):
        if name not in done:
            out = []
            for rule in lists[name]:
                kind, value, attrs = rule
                if kind != "include":
                    out.append(rule)
                    continue
                ref = value.lower()
                if ref in stack or ref not in lists or attrs:
                    report.note(f"geosite {name}: include:{value} not resolved (unknown list, a cycle or attributes)")
                    continue
                out += expand(ref, stack | {ref})
            done[name] = out
        return done[name]

    for name in list(lists):
        lists[name] = expand(name, {name})
