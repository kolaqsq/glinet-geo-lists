"""v2fly rule syntax: [kind:]value[:@attr]..."""


def parse_rule(text):
    """'domain:example.com:@cn' -> ('domain', 'example.com', {'cn'})."""
    text = text.split("#", 1)[0].strip()
    if not text:
        return None
    parts = text.split(":@")
    body, attrs = parts[0], frozenset(a.strip().lower() for a in parts[1:])
    kind, sep, value = body.partition(":")
    if not sep:
        kind, value = "domain", body
    return kind.strip().lower(), value.strip(), attrs


def parse_rule_file(text):
    return [r for r in map(parse_rule, text.splitlines()) if r]
