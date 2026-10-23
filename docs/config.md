# config.json reference

`config.json` controls what the build (`python3 -m glgeo` or `scripts/build.py`) downloads, how it converts it and which combined lists (presets) it publishes. Another file can be passed with `--config <path>`.

```json
{
  "options": { ... },
  "sources": {
    "geosite": [ { source }, ... ],
    "geoip":   [ { source }, ... ]
  },
  "presets": {
    "<name>": { preset }
  }
}
```

The build fails, and nothing is published, if a source cannot be downloaded or parsed, or if any guard below is triggered. This matters because an empty list on the router is dangerous. In "Exclude" mode an empty list sends all traffic through the VPN. In the reverse mode it sends all traffic around the VPN.

The config is checked before anything is downloaded. An unknown key (a typo such as `min_line`), a value of the wrong type, a negative number, an unknown source `type` or include kind, or a missing `file:` fails the build at once, with every problem listed. Defaults are those in the tables below.

## options

| Key | Type | Default | Effect |
|---|---|---|---|
| `allow_tld` | bool | `false` | Keep entries without a dot, i.e. whole top-level domains such as `domain:youtube` or `ru` (about 1300 of them in v2fly). With `false` they are dropped from every geosite list and preset. In a `file:` include such a line is an error. The GL.iNet importer rejects such lines (MT6000, 4.11.0), so keep `false` for lists meant for GL.iNet. |
| `max_shrink` | number 0–1 | `0.5` | Shrink guard, compared with the previous build. `0.5` means "lost more than half of its lines". The build fails if a **preset** has fewer lines than `previous × (1 − max_shrink)`, or if the total of all lists in `geosite/`, `geoip/` or `geoip6/` shrank that much: that catches a source that has broken but not become completely empty. A **single list** that shrank that much only gives a warning: upstream data really changes (in October 2026 `geoip6/kw.txt` went from 499 to 127 lines when Cloudflare WARP ranges were no longer placed in Kuwait), and failing would stop the updates of every other list. It needs the previous `index.json` (`--previous-index`). Without it the guard is skipped with a warning. |
| `shrink_min_lines` | int | `100` | The shrink guard only checks files (and directory totals) that had at least this many lines in the previous build. Small lists change a lot in normal operation (`geoip/telegram.txt` has 8 lines), so they are not checked. |
| `router_max_lines` | int | `200000` | Router limit guard. A preset with more lines fails the build: the GL.iNet importer checks only the first 200 000 lines of a file, and it is not known whether the rest is applied ([router.md](router.md#limits)). |
| `router_max_ips` | int | `55000` | Router limit guard. A preset with more IPv4 networks, or more IPv6 networks, fails the build. GL.iNet keeps each family in an ipset of 65 536 entries, and the IPs of resolved domains from the list go into the same set. When it is full, new entries are lost and domain rules silently stop working. The default leaves ~10 000 entries for domains. |

The router limits apply to presets only. Single geosite/geoip lists are published whatever their size, and the build log lists those over the limits. Where the limits come from: [router.md](router.md).

A file that existed in the previous build and is now missing produces a warning, not an error.

## sources

Two arrays: `geosite` (domain lists) and `geoip` (IP lists). Sources are processed in order. **If two sources publish a list with the same name, the first one wins.** The later source only adds names that are not taken yet. List names are lower-cased. Names that don't match `^[a-z0-9][a-z0-9!@._-]*$` are skipped.

Common keys:

| Key | Required | Effect |
|---|---|---|
| `name` | yes | Label used in log and error messages only. |
| `type` | yes | How to fetch and parse the source, see below. |
| `min_lists` | no (default `1`) | Guard: the minimum number of lists this source must **add**, counted after name collisions are resolved. Set it a bit below the normal number. Then a source that comes back nearly empty, or with a changed layout, fails the build instead of silently losing lists. |
| `max_age_days` | no (default `7`) | Staleness check: warn when the upstream data has not changed for more than this many days. `0` turns the check off, for lists that rarely change by design. The date is the `Last-Modified` header of the download, or the last commit for files on raw.githubusercontent.com and `github-dir` (one GitHub API request each). A stale source is a warning, not an error: its lists are still published, because failing would also stop the updates of every other list. Warnings show up as annotations and in the summary of the workflow run. |

### type `v2fly-plain-yml` (geosite)

The `dlc.dat_plain.yml` file from [v2fly/domain-list-community](https://github.com/v2fly/domain-list-community) releases. `include:` entries are already resolved in it. The build checks each list's rule count against its `length` field.

| Key | Effect |
|---|---|
| `url` | URL of the YAML file. |

### type `v2ray-dat` (geosite)

A binary v2ray/xray `geosite.dat` (protobuf `GeoSiteList`), read directly.

| Key | Effect |
|---|---|
| `url` | URL of the `.dat` file. |
| `sha256_url` | Optional. URL of a file whose first word is the SHA-256 of the `.dat` (the usual `.sha256sum` file). If set, the build fails when the checksum doesn't match, e.g. after a truncated download. |

### type `github-dir` (geosite and geoip)

Every file with the given extension in one directory of a GitHub repository. One file is one list, and the list name is the file name without the extension. The directory is listed through the GitHub API. Set `GITHUB_TOKEN` to avoid the anonymous rate limit of 60 requests/hour. Files are then downloaded in parallel. Lists already provided by an earlier source are not downloaded.

| Key | Default | Effect |
|---|---|---|
| `repo` | — | `owner/name`. |
| `ref` | — | Branch, tag or commit. |
| `path` | `""` | Directory inside the repository (`""` = root). |
| `ext` | `".txt"` | Only files with this extension are taken. |

File format:
- geosite: one rule per line, in v2fly syntax: `domain:`, `full:`, `keyword:`, `regexp:`, optional `:@attr`. A line without a prefix is `domain:`. `#` starts a comment.
- geoip: one IPv4/IPv6 address or CIDR per line, `#` comments. Invalid lines are skipped and counted in the log.

### type `url-lists` (geosite and geoip)

Lists from plain-text files at any URL. The config names each list and gives its files; a list made of several files is their union. A file used by several lists is downloaded once.

| Key | Default | Effect |
|---|---|---|
| `lists` | — | `{"<list name>": ["<url>", ...]}`. Names must match the list name pattern above. |
| `format` | `"rules"` | geosite only. `rules`: v2fly syntax as in `github-dir` (a plain domain per line works too). `hosts`: hosts-file lines `0.0.0.0 example.com`, each host becomes a domain. |

```json
{"name": "ru-blocked", "type": "url-lists", "max_age_days": 14, "lists": {
  "refilter": ["https://raw.githubusercontent.com/1andrevich/Re-filter-lists/refs/heads/main/domains_all.lst"],
  "ru-blocked": ["https://community.antifilter.download/list/domains.lst",
                 "https://raw.githubusercontent.com/1andrevich/Re-filter-lists/refs/heads/main/domains_all.lst"]}}
```

### `include:` rules

A geosite rule `include:<name>` is replaced by the rules of list `<name>`, whichever source provides it, as in v2fly. `dlc.dat_plain.yml` has its includes resolved already; plain-text sources may not (`ru-available-only-inside` includes `category-gov-ru`). An include of an unknown list, an include that closes a cycle, or one with attributes is dropped and noted in the log.

## presets

Combined lists published as `presets/<name>.txt`. The name must match `^[a-z0-9][a-z0-9._-]*$`. The router accepts one URL per policy, so anything that needs more than one list has to be a preset.

| Key | Required | Effect |
|---|---|---|
| `include` | yes | What goes into the preset, see below. An unknown list name fails the build. |
| `min_lines` | no (default `1`) | Guard: the minimum number of lines in the finished preset. Set it well below the normal size. It catches a preset that lost a whole component (e.g. `geoip:ru` came back empty). |
| `aggregate_ips` | no (default `false`) | If the preset has more IPv4 (or IPv6) networks than `options.router_max_ips`, merge nearby networks into wider ones until they fit. The merge adds as few extra addresses as possible, and the log shows how many. A network is never widened beyond /16 (IPv4) or /32 (IPv6). The extra addresses are matched by the policy too. That is harmless when listed traffic goes **through** the VPN (a few more hosts take the tunnel), but in Exclude mode it sends them around the VPN. Leave it off for Exclude presets. |
| `description` | no | Free text for people reading the config. The build doesn't use it. |

`include` items:

| Item | Adds |
|---|---|
| `geosite:<name>` | Domains of a geosite list. |
| `geosite:<name>@<attr>` | Only rules that have attribute `<attr>`, like `geosite:google@cn` in xray. |
| `geosite:<name>@!<attr>` | Only rules that do not have attribute `<attr>`. |
| `geoip:<name>` | IPv4 networks of a geoip list. |
| `geoip6:<name>` | IPv6 networks of a geoip list. |
| `file:<path>` | A local file, path relative to the directory of the config file (the repository root for the default `config.json`). One domain, IP or CIDR per line, `#` comments. Any other line fails the build. |

Output order: domains, then IPv4, then IPv6. Duplicates are removed, subdomains covered by a parent `domain:` entry are dropped, and networks are merged into the smallest set of CIDRs. With `aggregate_ips` networks are then widened as needed; the result is still sorted and non-overlapping. The build log shows the three counts for each preset.

## How rules are converted

These rules apply to every geosite list and preset. They are not configurable, except `allow_tld`. [router.md](router.md#how-the-build-shapes-lists) explains why, with figures.

- `domain:` and `full:` both become a plain domain line. On GL.iNet (dnsmasq) a line also matches subdomains, so `full:` becomes broader than in xray.
- `keyword:` and `regexp:` are dropped: GL.iNet has no equivalent.
- Domains are lower-cased, a trailing dot is removed, and internationalized names are converted to punycode (`рф` → `xn--p1ai`). Malformed entries are dropped. Labels with `_` (`_dmarc.example.com`) count as malformed, because the GL.iNet importer rejects them.
- The log line `geosite rules not representable in GL.iNet and dropped` shows how many rules were dropped and why.

## Adding a source type

A source type is a module in `glgeo/sources/` registered in `REGISTRY` (`glgeo/sources/__init__.py`). It defines:
- `KINDS`: which sections it can be used in, `"geosite"` and/or `"geoip"`;
- `KEYS`: its own config keys, `{key: (type, default)}`, with `REQUIRED` as the default for mandatory keys. The config check uses this, so the new keys are validated automatically;
- `load(src, kind, wanted)`: returns `{list name: data}`. The data is a list of `(kind, value, attrs)` rules for geosite and an `IpSet` for geoip. `wanted(name)` tells whether a list would be kept, so a source can skip downloading the others;
- `updated(src)`: called after `load()`, returns `[(what, datetime or None)]`: when the upstream data last changed. `net.last_modified(url)` and `net.github_commit_date()` cover the usual cases. Used by `max_age_days`;
- `check(src)`, optional: extra config checks beyond `KEYS`, returns a list of error messages.

Name collisions, the name pattern, `min_lists` and `max_age_days` are handled in one place, `load_all`. Parsers that don't touch the network go to `glgeo/formats/`.
