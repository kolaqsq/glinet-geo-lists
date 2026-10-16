from ..errors import BuildError
from .protobuf import fields

# v2ray router.Domain.Type
DAT_KINDS = {0: "keyword", 1: "regexp", 2: "domain", 3: "full"}


def parse_geosite_dat(data):
    """Parse v2ray geosite.dat (GeoSiteList protobuf) without the protobuf package.
    GeoSiteList{1: GeoSite}, GeoSite{1: country_code, 2: Domain},
    Domain{1: type, 2: value, 3: Attribute{1: key}}."""
    try:
        return _parse(data)
    except (IndexError, UnicodeDecodeError) as e:
        raise BuildError(f"geosite.dat: malformed ({e})") from e


def _parse(data):
    lists = {}
    for num, wire, span in fields(data, 0, len(data)):
        if num != 1 or wire != 2:
            continue
        name, rules = None, []
        for n2, w2, v2 in fields(data, *span):
            if n2 == 1 and w2 == 2:
                name = data[v2[0]:v2[1]].decode("utf-8")
            elif n2 == 2 and w2 == 2:
                kind, value, attrs = 0, "", []
                for n3, w3, v3 in fields(data, *v2):
                    if n3 == 1 and w3 == 0:
                        kind = v3
                    elif n3 == 2 and w3 == 2:
                        value = data[v3[0]:v3[1]].decode("utf-8")
                    elif n3 == 3 and w3 == 2:
                        for n4, w4, v4 in fields(data, *v3):
                            if n4 == 1 and w4 == 2:
                                attrs.append(data[v4[0]:v4[1]].decode("utf-8").lower())
                if kind not in DAT_KINDS:
                    raise BuildError(f"geosite.dat: unknown domain type {kind}")
                rules.append((DAT_KINDS[kind], value, frozenset(attrs)))
        if name is None:
            raise BuildError("geosite.dat: entry without country_code")
        lists[name.lower()] = rules
    return lists
