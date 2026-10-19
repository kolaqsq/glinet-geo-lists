import ipaddress


def parse_hosts_file(text):
    """hosts(5) lines '0.0.0.0 example.com' -> domain: rules. A hosts entry names one host, but on
    GL.iNet every line covers its subdomains anyway, and domain: lets the build drop redundant children."""
    rules = []
    for line in text.splitlines():
        fields = line.split("#", 1)[0].split()
        if len(fields) < 2:
            continue
        try:
            ipaddress.ip_address(fields[0])
        except ValueError:
            continue
        rules += [("domain", host, frozenset()) for host in fields[1:]]
    return rules
