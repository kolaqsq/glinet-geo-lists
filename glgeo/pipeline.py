"""config -> sources -> lists -> presets -> guards -> index."""

import collections
import os

from . import config, guards, net, output, sources
from .errors import BuildError
from .log import log
from .model import DomainSet
from .presets import Context, build_preset
from .report import Report


def run(config_path, out_dir, previous_index=None, cache_dir=None, report=None):
    report = report if report is not None else Report()
    cfg = config.load(config_path)
    opts = cfg["options"]
    net.set_cache_dir(cache_dir)

    geosite = sources.load_all("geosite", cfg["sources"]["geosite"], report)
    sources.resolve_includes(geosite, report)
    geoip = sources.load_all("geoip", cfg["sources"]["geoip"], report)
    previous = guards.load_previous_index(previous_index, report)
    previous_files = previous["files"] if previous else {}

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
        report.note(f"{len(over_limit)} lists exceed GL.iNet limits and would be cut on the router: {', '.join(over_limit)}")

    errors = []
    ctx = Context(geosite, geoip, opts["allow_tld"], os.path.dirname(os.path.abspath(config_path)), opts["router_max_ips"])
    for name, preset in sorted(cfg["presets"].items()):
        domains, v4, v6 = build_preset(name, preset, ctx)
        rel = f"presets/{name}.txt"
        output.write_list(out_dir, rel, domains + v4 + v6, index)
        log(f"preset {name}: {index[rel]} lines ({len(domains)} domains, {len(v4)} IPv4, {len(v6)} IPv6)")
        report.presets.append((name, index[rel], len(domains), len(v4), len(v6), previous_files.get(rel)))
        errors += guards.check_min_lines(rel, index[rel], preset["min_lines"])
        errors += [f"{rel}: {p}" for p in guards.router_limit_problems(index[rel], len(v4), len(v6), opts)]

    if previous:
        errors += guards.check_shrink(index, previous_files, opts["max_shrink"], opts["shrink_min_lines"], report)
        changed = sum(1 for rel, n in index.items() if rel in previous_files and previous_files[rel] != n)
        report.changes = (changed, len(index.keys() - previous_files.keys()),
                          len(previous_files.keys() - index.keys()), previous.get("generated", "unknown"))

    output.write_index(out_dir, index)
    report.lists = len(index)
    log(f"wrote {len(index)} lists to {out_dir}")

    if errors:
        raise BuildError("guard failed:\n  " + "\n  ".join(errors))
