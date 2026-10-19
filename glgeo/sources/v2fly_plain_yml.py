"""dlc.dat_plain.yml from v2fly/domain-list-community releases."""

from .. import net
from ..config import REQUIRED
from ..formats.plain_yml import parse_plain_yml

KINDS = ("geosite",)
KEYS = {"url": (str, REQUIRED)}


def load(src, kind, wanted):
    return parse_plain_yml(net.http_get(src["url"]))


def updated(src):
    return [(src["url"], net.last_modified(src["url"]))]
