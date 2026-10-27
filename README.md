# glinet-geo-lists

geoip / geosite lists as plain text for GL.iNet routers — the equivalent of `geoip.dat` / `geosite.dat` for xray and rule-sets for sing-box.

GL.iNet firmware does not support geoip/geosite, but since 4.7 its VPN Policy can import rules from an online text file: one entry per line, a domain or an IPv4 CIDR. This repository rebuilds such files daily from the same sources xray and sing-box use.

## Usage

VPN Dashboard → Policy Mode → "Exclude specified Domain / IP List" (listed traffic bypasses the VPN) or the opposite mode (only listed traffic goes through the VPN) → paste a list URL.

URLs (branch `release`, rebuilt daily at 16:00 UTC; the router fetches a list at 03:00 its time):

```
https://raw.githubusercontent.com/kolaqsq/glinet-geo-lists/release/<path>
https://cdn.jsdelivr.net/gh/kolaqsq/glinet-geo-lists@release/<path>
```

raw.githubusercontent.com serves a new build within ~5 minutes. jsDelivr caches a branch for up to 12 hours and does not serve files over 20 MB; use it if raw.githubusercontent.com is unreachable from the router.

| Path | Contents | xray equivalent |
|---|---|---|
| `geosite/<name>.txt` | domains of a category from v2fly/domain-list-community, or of a list from the other sources below | `geosite:<name>` |
| `geoip/<name>.txt` | IPv4 CIDRs of a country or service | `geoip:<name>` (IPv4 only) |
| `geoip6/<name>.txt` | IPv6 CIDRs | `geoip:<name>` (IPv6 only) |
| `presets/<name>.txt` | ready-made combinations defined in `config.json` | — |
| `index.json` | every published file with its line count | — |

A policy takes a single URL, so combinations like "geoip:ru + geosite:category-ru" are built as presets.

## Presets

| Preset | Mode | Contents |
|---|---|---|
| `ru-direct` | Exclude: Russian traffic goes direct, everything else through the VPN | geosite: category-ru, category-gov-ru, ru-available-only-inside, the Russian sector categories (category-bank-ru, -ecommerce-ru, -retail-ru, -media-ru, -entertainment-ru, -travel-ru, -education-ru, -medicine-ru, -forums-ru, -tech-media-ru, -ai-ru), yandex, mailru, vk, 2gis, avito, cian, headhunter, rutube, kinopoisk + geoip:ru |
| `ru-direct-ip` | Exclude, for routers where domain rules don't work | geoip:ru |
| `ru-blocked` | Opposite mode: only listed traffic goes through the VPN. Popular services blocked or throttled in Russia (~1.5K lines) | geosite:antifilter-download-community (curated by the antifilter.download community) + geosite:youtube + geosite:telegram + geoip:telegram + geoip:ru-blocked-community + geosite:ookla-speedtest (Speedtest by Ookla: site and API; the test servers themselves are run by ISPs, some of them in Russia). Covers big services only; the community list itself has a few adult sites |
| `ru-blocked-dev` | Opposite mode. Everything in `ru-blocked` plus AI, developer, software and streaming services that block Russian users (~3.2K lines) | `ru-blocked` + geosite: category-ai-!cn (OpenAI, Anthropic, Gemini, Perplexity, xAI, Cursor, …), jetbrains, hashicorp, docker, gitlab, atlassian, notion, figma, canva, discord, autodesk, adobe, oracle, unity, intel, nvidia, amd, netflix, spotify, disney, hbo, primevideo |

The router takes a single URL, so pick one of the two: `ru-blocked-dev` already contains `ru-blocked`. The whole Roskomnadzor registry is not offered as a preset: it is ~75K domains and ~89K networks, most of them scam, gambling, piracy and adult sites, and it does not fit the router (see below). It is still published as `geosite/ru-blocked.txt` and `geoip/ru-blocked.txt`.

To add a preset, edit the `presets` section of `config.json`. Items of `include`:
- `geosite:<name>`, `geosite:<name>@<attr>` or `geosite:<name>@!<attr>` (like `geosite:google@cn` in xray);
- `geoip:<name>` (IPv4), `geoip6:<name>` (IPv6);
- `file:<path>`: your own file with domains and IPs.

All config keys (sources, options, guards) are described in [docs/config.md](docs/config.md).

## Router limits and conversion

[docs/router.md](docs/router.md) explains how GL.iNet applies a list (domains become dnsmasq rules that fill an ipset as clients resolve them), which entries it accepts, its limits and how the build shapes lists to fit. In short, measured on a Flint 2 (GL-MT6000), firmware 4.11.0:

- An entry covers its subdomains, so `domain:` and `full:` both become a plain line, and subdomains under a listed parent are dropped. `keyword:`, `regexp:`, whole zones (`ru`) and labels with `_` are not accepted and are dropped.
- The importer checks only the first 200 000 lines; whether longer files are applied in full is not proven.
- Networks from the list and IPs of resolved domains share an ipset of 65 536 entries per family. When it is full, rules silently stop working.
- Very large domain lists can stall the router's DNS while they load.

Presets are checked against these limits. A preset with `"aggregate_ips": true` merges nearby networks until they fit, at the cost of a few extra addresses (+6.7% for the 88.6K networks of `geoip:ru-blocked`). Single geosite/geoip lists are published whatever their size; the largest, `geosite/ru-blocked-all.txt` and `geosite/antifilter-download.txt` (~1.55M lines, ~29 MB each), are far over the limits. jsDelivr does not serve files over 20 MB, so use the raw.githubusercontent.com URL for them.

## Safeguards against empty lists

In Exclude mode an empty list sends all traffic through the VPN; in the opposite mode it sends all traffic outside the VPN. The build fails and publishes nothing if:
- a source is unreachable or yields fewer lists than its `min_lists`;
- a preset is shorter than its `min_lines`;
- a preset exceeds the router limits above;
- a preset, or the total of all `geosite/`, `geoip/` or `geoip6/` lists, shrinks by more than `options.max_shrink` (50%) compared with the previous build. A single list that shrinks that much only gives a warning.

A source whose data has not changed for longer than its `max_age_days` does not fail the build: its lists are still published, and the build reports a warning. Each run of the GitHub workflow shows a summary with presets, sources and their last update, warnings and errors.

`config.json` is checked before anything is downloaded: an unknown key, a wrong type or a malformed `include` item fails the build at once.

## Caveats

- Domain rules only work when clients use the router's DNS (no DoH/DoT in browsers or the OS). They work through the IPs of the domain, so other sites on a shared CDN IP follow the same rule.
- An IPv6 line does not break the list, but routing IPv6 through the policy is untested. With IPv6 enabled, traffic may bypass the VPN.
- Invalid lines are skipped one by one; the rest of the list still applies. Lines starting with `#` are fine.
- The router refreshes the list once a day at 03:00 (its local time) with `/usr/bin/update_vpn_domain.sh`, and only downloads it when the file has changed. On a router upgraded from older firmware the cron job may be a leftover that does nothing, so the list is never refreshed: see [docs/router.md](docs/router.md#checking-on-your-router) for how to check and fix it.

## Building locally

```bash
python3 -m unittest discover -s tests
python3 -m glgeo --out out --cache-dir .cache
```

`scripts/build.py` does the same as `python3 -m glgeo`. `--cache-dir` keeps every download and reuses it later, so after the first run (~75 s) a rebuild runs offline in ~20 s. That's handy for trying preset changes. Without it, everything is downloaded again. `--summary <file>` appends a Markdown summary of the build to the file; the workflow passes `$GITHUB_STEP_SUMMARY`, so it shows on the run page.

Requires Python 3.9+, no third-party packages. Code layout:

| Module | Role |
|---|---|
| `glgeo/config.py` | loads `config.json`, checks it against the schema, fills defaults |
| `glgeo/net.py` | downloads, download cache, checksums, GitHub directory listing |
| `glgeo/formats/` | pure parsers: v2fly rules, `dlc.dat_plain.yml`, protobuf / `geosite.dat`, hosts files, IP lists |
| `glgeo/sources/` | one module per source `type` plus `REGISTRY`; `load_all` resolves name collisions, `min_lists` and `max_age_days`; v2fly `include:` rules are resolved across sources |
| `glgeo/model.py` | `DomainSet`, `IpSet`: normalisation and the GL.iNet form |
| `glgeo/presets.py` | `include` kinds (`geosite`, `geoip`, `geoip6`, `file`) and preset assembly |
| `glgeo/guards.py`, `glgeo/output.py` | guards, writing lists and `index.json` |
| `glgeo/pipeline.py` | config → sources → lists → presets → guards → index |
| `glgeo/report.py` | warnings, GitHub annotations and the run summary (`--summary`) |

A new source type is a module in `glgeo/sources/` with `KINDS`, `KEYS`, `load()` and `updated()`, plus a line in `REGISTRY`.

## Sources

Domain lists:
- [v2fly/domain-list-community](https://github.com/v2fly/domain-list-community): `dlc.dat_plain.yml` from releases, all categories.
- [antifilter.download](https://antifilter.download) → `antifilter-download` (the whole Roskomnadzor registry), [community.antifilter.download](https://community.antifilter.download) → `antifilter-download-community` (popular services, curated by the community), [Re:filter](https://github.com/1andrevich/Re-filter-lists) → `refilter`. Combined like in runetfreedom: `ru-blocked` = community + refilter, `ru-blocked-all` = all three.
- [runetfreedom/russia-domains-list](https://github.com/runetfreedom/russia-domains-list) → `ru-available-only-inside` (sites that work only from Russian IPs; it includes v2fly `category-gov-ru`).
- [Loyalsoldier/v2ray-rules-dat](https://github.com/Loyalsoldier/v2ray-rules-dat) → `gfw`.
- [WindowsSpyBlocker](https://github.com/crazy-max/WindowsSpyBlocker) hosts files → `win-spy`, `win-update`, `win-extra`.

These are the upstreams of [runetfreedom/russia-blocked-geosite](https://github.com/runetfreedom/russia-blocked-geosite), read directly: its `geosite.dat` has not been rebuilt since 2026-08-10.

IP lists:
- [Loyalsoldier/geoip](https://github.com/Loyalsoldier/geoip): countries (GeoLite2 and others) and services (telegram, google, cloudflare, …)
- [runetfreedom/russia-blocked-geoip](https://github.com/runetfreedom/russia-blocked-geoip): ru-blocked, ru-whitelist, yandex and others

## License

The build code is under the [MIT License](LICENSE).

The published lists are not: each keeps the license of its source, see [NOTICE](NOTICE). NOTICE and the GPL-3.0 text ([COPYING.GPL-3.0](COPYING.GPL-3.0)) are also copied to the `release` branch.

| Lists | Source | License |
|---|---|---|
| `geosite/*` | v2fly/domain-list-community | MIT |
| `geosite/antifilter-download`, `antifilter-download-community` | antifilter.download | not stated |
| `geosite/refilter` | Re:filter | MIT |
| `geosite/ru-blocked`, `ru-blocked-all` | antifilter.download + Re:filter | not stated (antifilter) and MIT |
| `geosite/ru-available-only-inside` | runetfreedom/russia-domains-list | no license file; runetfreedom distributes it under GPL-3.0 |
| `geosite/gfw` | Loyalsoldier/v2ray-rules-dat | GPL-3.0 |
| `geosite/win-*` | WindowsSpyBlocker | MIT |
| `geoip/ru-blocked`, `ru-blocked-community`, `ru-whitelist`, `re-filter`, `ddos-guard`, `yandex` | runetfreedom/russia-blocked-geoip | GPL-3.0 |
| other `geoip/*`, `geoip6/*` | Loyalsoldier/geoip, based on MaxMind GeoLite2 | CC BY-SA 4.0, GeoLite EULA |
| `presets/ru-direct`, `presets/ru-blocked`, `presets/ru-blocked-dev` | mixed, includes runetfreedom | GPL-3.0 |
| `presets/ru-direct-ip` | Loyalsoldier/geoip | CC BY-SA 4.0 |

This product includes GeoLite Data created by MaxMind, available from https://www.maxmind.com. The GeoLite EULA requires deleting old copies within 30 days of a new release, so if you mirror the lists, keep the mirror updated.
