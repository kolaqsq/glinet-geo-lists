"""One file per list in a directory of a GitHub repository."""

from .. import net
from ..config import REQUIRED
from ..formats.iplist import parse_ip_file
from ..formats.rules import parse_rule_file
from ..log import log
from ..model import IpSet

KINDS = ("geosite", "geoip")
KEYS = {"repo": (str, REQUIRED), "ref": (str, REQUIRED), "path": (str, ""), "ext": (str, ".txt")}


def load(src, kind, wanted):
    files = net.github_dir(src["repo"], src["ref"], src["path"], src["ext"])
    urls = {name: url for name, url in files.items() if wanted(name)}
    texts = net.download_all(list(urls.values()))
    if kind == "geosite":
        return {name: parse_rule_file(texts[url]) for name, url in urls.items()}
    result = {}
    for name, url in urls.items():
        v4, v6, bad = parse_ip_file(texts[url])
        if bad:
            log(f"geoip {name}: {bad} invalid lines skipped")
        result[name] = IpSet(v4, v6)
    return result


def updated(src):
    where = f"{src['repo']}@{src['ref']}" + (f"/{src['path']}" if src["path"] else "")
    return [(where, net.github_commit_date(src["repo"], src["ref"], src["path"]))]
