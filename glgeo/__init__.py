"""Convert geoip/geosite sources into plain-text lists for GL.iNet VPN Policy.

GL.iNet (firmware 4.7+) imports domain/IP rules from an online text file: one domain
or IPv4 CIDR per line. This package turns the usual xray/sing-box sources into such files.

Output layout (--out):
  geoip/<name>.txt     IPv4 CIDR, aggregated
  geoip6/<name>.txt    IPv6 CIDR, aggregated (only for lists that have IPv6)
  geosite/<name>.txt   domains (an entry covers its subdomains, like dnsmasq)
  presets/<name>.txt   combinations defined in config.json
  index.json           line counts, used by the shrink guard on the next build

Python 3.9+, stdlib only.
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
