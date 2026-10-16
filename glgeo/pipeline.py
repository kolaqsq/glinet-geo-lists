"""config -> sources -> lists -> presets -> guards -> index."""

import collections
import os

from . import config, guards, net, output, sources
from .errors import BuildError
from .log import log
from .model import DomainSet
from .presets import Context, build_preset


def run(config_path, out_dir, previous_index=None, cache_dir=None):
    cfg = config.load(config_path)
    opts = cfg["options"]
    net.set_cache_dir(cache_dir)

    geosite = sources.load_all("geosite", cfg["sources"]["geosite"])
    geoip = sources.load_all("geoip", cfg["sources"]["geoip"])

    output.clean(out_dir)
    index = {}
    over_limit = []

    dropped = collections.Counter()
    for name, rules in sorted(geosite.items()):
        ds = DomainSet()
        ds.add_rules(rules, None, opts["allow_tld"])
        dropped.update(ds.dropped)
        lines = ds.compact()
        if lines:
            rel = f"geosite/{name}.txt"
            output.write_list(out_dir, rel, lines, index)
            if guards.router_limit_problems(len(lines), 0, 0, opts):
                over_limit.append(rel)
    log(f"geosite rules not representable in GL.iNet and dropped: {dict(dropped)}")

    for name, ips in sorted(geoip.items()):
        v4, v6 = ips.compact4(), ips.compact6()
        for rel, lines, counts in ((f"geoip/{name}.txt", v4, (len(v4), 0)),
                                   (f"geoip6/{name}.txt", v6, (0, len(v6)))):
            if lines:
                output.write_list(out_dir, rel, lines, index)
                if guards.router_limit_problems(len(lines), *counts, opts):
                    over_limit.append(rel)
    if over_limit:
        shown = ", ".join(over_limit[:10]) + (f" (+{len(over_limit) - 10} more)" if len(over_limit) > 10 else "")
        log(f"NOTE: {len(over_limit)} lists exceed GL.iNet limits and would be cut on the router: {shown}")

    errors = []
    ctx = Context(geosite, geoip, opts["allow_tld"], os.path.dirname(os.path.abspath(config_path)), opts["router_max_ips"])
    for name, preset in sorted(cfg["presets"].items()):
        domains, v4, v6 = build_preset(name, preset, ctx)
        rel = f"presets/{name}.txt"
        output.write_list(out_dir, rel, domains + v4 + v6, index)
        log(f"preset {name}: {index[rel]} lines ({len(domains)} domains, {len(v4)} IPv4, {len(v6)} IPv6)")
        errors += guards.check_min_lines(rel, index[rel], preset["min_lines"])
        errors += [f"{rel}: {p}" for p in guards.router_limit_problems(index[rel], len(v4), len(v6), opts)]

    previous = guards.load_previous_index(previous_index)
    if previous:
        errors += guards.check_shrink(index, previous, opts["max_shrink"], opts["shrink_min_lines"])

    output.write_index(out_dir, index)
    log(f"wrote {len(index)} lists to {out_dir}")

    if errors:
        raise BuildError("guard failed:\n  " + "\n  ".join(errors))
