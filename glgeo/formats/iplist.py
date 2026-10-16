import ipaddress


def parse_ip_file(text):
    """One address or CIDR per line, '#' comments. Returns (ipv4 nets, ipv6 nets, invalid line count)."""
    v4, v6, bad = [], [], 0
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        try:
            net = ipaddress.ip_network(line, strict=False)
        except ValueError:
            bad += 1
            continue
        (v4 if net.version == 4 else v6).append(net)
    return v4, v6, bad
