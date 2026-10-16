"""In-memory lists and the conversion to what GL.iNet accepts."""

import collections
import ipaddress
import re

# GL.iNet rejects labels with "_" (MT6000, 4.11.0), so unlike in DNS they are invalid here.
DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)


def norm_domain(value):
    value = value.strip().lower().rstrip(".")
    if not value.isascii():
        try:
            value = value.encode("idna").decode("ascii")
        except UnicodeError:
            return None
    return value if DOMAIN_RE.match(value) else None


def attr_ok(attrs, attr_filter):
    if not attr_filter:
        return True
    if attr_filter.startswith("!"):
        return attr_filter[1:] not in attrs
    return attr_filter in attrs


class DomainSet:
    """Domains in GL/dnsmasq form. wildcard=True means the entry also covers subdomains
    on the source side (domain:), so children of it can be dropped."""

    def __init__(self):
        self.items = {}
        self.dropped = collections.Counter()

    def add(self, domain, wildcard):
        self.items[domain] = self.items.get(domain, False) or wildcard

    def add_rules(self, rules, attr_filter, allow_tld):
        for kind, value, attrs in rules:
            if not attr_ok(attrs, attr_filter):
                continue
            if kind not in ("domain", "full"):
                self.dropped[kind] += 1
                continue
            d = norm_domain(value)
            if d is None:
                self.dropped["invalid"] += 1
            elif "." not in d and not allow_tld:
                self.dropped["tld"] += 1
            else:
                self.add(d, kind == "domain")

    def update(self, other):
        for d, w in other.items.items():
            self.add(d, w)
        self.dropped.update(other.dropped)

    def compact(self):
        wild = {d for d, w in self.items.items() if w}
        out = []
        for d in self.items:
            labels = d.split(".")
            if any(".".join(labels[i:]) in wild for i in range(1, len(labels))):
                continue
            out.append(d)
        return sorted(out)


class IpSet:
    """IPv4 and IPv6 networks kept apart: GL.iNet puts them into separate ipsets."""

    def __init__(self, v4=(), v6=()):
        self.v4 = list(v4)
        self.v6 = list(v6)

    def update(self, other):
        self.v4 += other.v4
        self.v6 += other.v6

    def compact4(self):
        return collapse(self.v4)

    def compact6(self):
        return collapse(self.v6)


def collapse(nets):
    return [str(n) for n in ipaddress.collapse_addresses(nets)]


def fit_networks(nets, budget, min_prefix):
    """Merge networks of one family into at most budget entries, adding as few extra addresses
    as possible. A network is never widened beyond /min_prefix. Returns (networks, extra addresses);
    if the budget can't be met, returns the smallest result possible.

    Exact for a given price per entry (lam): a tree DP over the address trie decides at each node
    whether one network covering the whole node is cheaper than the best covering of its halves.
    A binary search over lam finds the smallest price that meets the budget."""
    nets = list(ipaddress.collapse_addresses(nets))
    if len(nets) <= budget:
        return nets, 0
    cls = type(nets[0])
    bits = nets[0].max_prefixlen
    shift = bits - min_prefix
    wide, groups = [], {}
    for n in nets:
        if n.prefixlen <= min_prefix:
            wide.append((int(n.network_address), n.prefixlen))
        else:
            groups.setdefault(int(n.network_address) >> shift, []).append((int(n.network_address), n.prefixlen))

    def solve(items, lam, base, plen):
        """-> (score, [(addr, prefixlen)], extra) for items sorted and all inside base/plen."""
        if len(items) == 1 and items[0][1] == plen:
            return lam, items, 0
        size = 1 << (bits - plen)
        half = base + size // 2
        split = next((i for i, (a, _) in enumerate(items) if a >= half), len(items))
        score, chosen, extra = 0, [], 0
        for part, part_base in ((items[:split], base), (items[split:], half)):
            if part:
                s, c, e = solve(part, lam, part_base, plen + 1)
                score, chosen, extra = score + s, chosen + c, extra + e
        gap = size - sum(1 << (bits - p) for _, p in items)
        if gap + lam < score:
            return gap + lam, [(base, plen)], gap
        return score, chosen, extra

    def run(lam):
        chosen, extra = list(wide), 0
        for key in sorted(groups):
            _, c, e = solve(groups[key], lam, key << shift, min_prefix)
            chosen += c
            extra += e
        return chosen, extra

    lo, hi = 0, (1 << shift) + 1  # at hi every group collapses to one /min_prefix network
    best = run(hi)
    if len(best[0]) > budget:
        return [cls(c) for c in sorted(best[0])], best[1]
    while hi - lo > 1:
        mid = (lo + hi) // 2
        result = run(mid)
        if len(result[0]) <= budget:
            hi, best = mid, result
        else:
            lo = mid
    return list(ipaddress.collapse_addresses(cls(c) for c in best[0])), best[1]
