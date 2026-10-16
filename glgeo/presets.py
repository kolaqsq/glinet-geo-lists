"""Presets: one published list combined from several geosite/geoip lists and local files.

Each include kind provides check(ref, base_dir) -> error or None, used by config validation
before anything is downloaded, and apply(ref, ctx, acc). A new kind is a new class plus a
line in INCLUDE_KINDS.
"""

import ipaddress
import os

from .errors import BuildError
from .log import log
from .model import DomainSet, IpSet, fit_networks, norm_domain
from .sources import NAME_RE

ATTR_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789._-")
# aggregate_ips never widens a network beyond these: a /16 of IPv4 or /32 of IPv6 is already a whole provider
MIN_PREFIX = {"IPv4": 16, "IPv6": 32}


class Context:
    def __init__(self, geosite, geoip, allow_tld, base_dir, max_ips):
        self.geosite = geosite
        self.geoip = geoip
        self.allow_tld = allow_tld
        self.base_dir = base_dir
        self.max_ips = max_ips


class Acc:
    def __init__(self):
        self.domains = DomainSet()
        self.ips = IpSet()


class GeositeInclude:
    """geosite:<name>, geosite:<name>@<attr>, geosite:<name>@!<attr>"""

    def check(self, ref, base_dir):
        name, at, attr = ref.partition("@")
        if not NAME_RE.match(name):
            return f"bad geosite list name {name!r}"
        if at and not (attr.lstrip("!") and set(attr.lstrip("!")) <= ATTR_CHARS):
            return f"bad attribute filter {attr!r}"
        return None

    def apply(self, ref, ctx, acc, preset):
        name, _, attr = ref.partition("@")
        if name not in ctx.geosite:
            raise BuildError(f"preset {preset}: unknown geosite list {name!r}")
        part = DomainSet()
        part.add_rules(ctx.geosite[name], attr, ctx.allow_tld)
        acc.domains.update(part)


class GeoipInclude:
    """geoip:<name> takes the IPv4 networks of a list, geoip6:<name> the IPv6 ones."""

    def __init__(self, v6):
        self.v6 = v6

    def check(self, ref, base_dir):
        return None if NAME_RE.match(ref) else f"bad geoip list name {ref!r}"

    def apply(self, ref, ctx, acc, preset):
        if ref not in ctx.geoip:
            raise BuildError(f"preset {preset}: unknown geoip list {ref!r}")
        ips = ctx.geoip[ref]
        acc.ips.update(IpSet(v6=ips.v6) if self.v6 else IpSet(v4=ips.v4))


class FileInclude:
    """file:<path>, relative to the config file. Domains and IPs mixed, one per line, '#' comments."""

    def check(self, ref, base_dir):
        return None if os.path.isfile(os.path.join(base_dir, ref)) else f"file not found: {ref}"

    def apply(self, ref, ctx, acc, preset):
        with open(os.path.join(ctx.base_dir, ref), encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
                try:
                    net = ipaddress.ip_network(line, strict=False)
                    acc.ips.update(IpSet(v4=[net]) if net.version == 4 else IpSet(v6=[net]))
                    continue
                except ValueError:
                    pass
                d = norm_domain(line)
                if d is None or ("." not in d and not ctx.allow_tld):
                    raise BuildError(f"{ref}:{n}: not a domain or IP: {line!r}")
                acc.domains.add(d, True)


INCLUDE_KINDS = {
    "geosite": GeositeInclude(),
    "geoip": GeoipInclude(v6=False),
    "geoip6": GeoipInclude(v6=True),
    "file": FileInclude(),
}


def check_include(item, base_dir):
    if not isinstance(item, str):
        return f"expected a string, got {item!r}"
    kind, sep, ref = item.partition(":")
    if not sep or kind not in INCLUDE_KINDS:
        return f"{item!r}: expected <kind>:<name>, kind one of: {', '.join(INCLUDE_KINDS)}"
    if not ref:
        return f"{item!r}: empty name"
    return INCLUDE_KINDS[kind].check(ref, base_dir)


def build_preset(name, preset, ctx):
    """Returns (domain lines, IPv4 lines, IPv6 lines); the published file is them in that order."""
    acc = Acc()
    for item in preset["include"]:
        kind, _, ref = item.partition(":")
        INCLUDE_KINDS[kind].apply(ref, ctx, acc, name)
    v4, v6 = acc.ips.compact4(), acc.ips.compact6()
    if preset["aggregate_ips"]:
        v4 = _aggregate(name, "IPv4", acc.ips.v4, v4, ctx.max_ips)
        v6 = _aggregate(name, "IPv6", acc.ips.v6, v6, ctx.max_ips)
    return acc.domains.compact(), v4, v6


def _aggregate(preset, family, nets, lines, budget):
    """Widen networks so that they fit into the router's ipset; the extra addresses are matched too."""
    if len(lines) <= budget:
        return lines
    fitted, extra = fit_networks(nets, budget, MIN_PREFIX[family])
    total = sum(n.num_addresses for n in fitted) - extra
    log(f"preset {preset}: {family} {len(lines)} -> {len(fitted)} networks to fit router_max_ips, "
        f"{extra} extra addresses (+{100 * extra / total:.1f}%)")
    return [str(n) for n in fitted]
