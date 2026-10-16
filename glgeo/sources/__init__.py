"""Source types. Each module provides:

  KINDS  list kinds it can feed: "geosite" (data = list of rules) and/or "geoip" (data = IpSet)
  KEYS   its config keys: {key: (type, default)}, default REQUIRED for mandatory keys
  load(src, kind, wanted) -> {name: data}
         wanted(name) tells whether a list would be used; skip downloading the others

A new type is a new module plus a line in REGISTRY.
"""

import re

from ..errors import BuildError
from ..log import log
from . import github_dir, v2fly_plain_yml, v2ray_dat

REGISTRY = {
    "v2fly-plain-yml": v2fly_plain_yml,
    "v2ray-dat": v2ray_dat,
    "github-dir": github_dir,
}

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9!@._-]*$")


def load_all(kind, sources):
    """Returns {name: data}; an earlier source wins on name collisions."""
    result = {}

    def wanted(name):
        return name not in result and bool(NAME_RE.match(name))

    for src in sources:
        lists = REGISTRY[src["type"]].load(src, kind, wanted)
        added = 0
        for name, data in lists.items():
            if wanted(name):
                result[name] = data
                added += 1
        log(f"{kind} {src['name']}: {len(lists)} lists, {added} added")
        if added < src["min_lists"]:
            raise BuildError(f"{kind} {src['name']}: only {added} lists added, expected at least {src['min_lists']}")
    return result
