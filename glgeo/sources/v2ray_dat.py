"""Binary v2ray/xray geosite.dat, optionally checked against a .sha256sum file."""

from .. import net
from ..config import REQUIRED
from ..formats.geosite_dat import parse_geosite_dat

KINDS = ("geosite",)
KEYS = {"url": (str, REQUIRED), "sha256_url": (str, None)}


def load(src, kind, wanted):
    return parse_geosite_dat(net.fetch_checked(src["url"], src["sha256_url"]))
