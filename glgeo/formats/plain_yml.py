import re

from ..errors import BuildError
from .rules import parse_rule


def parse_plain_yml(text):
    """Parse v2fly dlc.dat_plain.yml (includes already resolved) without PyYAML."""
    lists, expected, cur = {}, {}, None
    for line in text.splitlines():
        if not line.strip() or line.strip() in ("lists:", "rules:"):
            continue
        m = re.match(r'^  - name: "?([^"]+)"?$', line)
        if m:
            cur = m.group(1).lower()
            lists[cur] = []
            continue
        m = re.match(r"^    length: (\d+)$", line)
        if m and cur:
            expected[cur] = int(m.group(1))
            continue
        m = re.match(r'^      - "(.*)"$', line)
        if m and cur:
            rule = parse_rule(m.group(1))
            if rule:
                lists[cur].append(rule)
            continue
        raise BuildError(f"plain yml: unexpected line {line!r}")
    for name, count in expected.items():
        if len(lists[name]) != count:
            raise BuildError(f"plain yml: {name} has {len(lists[name])} rules, length says {count}")
    return lists
