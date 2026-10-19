import concurrent.futures
import datetime
import email.utils
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from .errors import BuildError

USER_AGENT = "glinet-geo-lists"

_cache_dir = None
_last_modified = {}  # url -> Last-Modified header of the response it was downloaded from

RAW_GITHUB_RE = re.compile(r"^https://raw\.githubusercontent\.com/([^/]+/[^/]+)/(?:refs/heads/)?([^/]+)/(.+)$")


def set_cache_dir(path):
    """Keep every download in path and reuse it on later runs, so a rebuild works offline."""
    global _cache_dir
    _cache_dir = path
    if path:
        os.makedirs(path, exist_ok=True)


def cache_path(cache_dir, url):
    return os.path.join(cache_dir, hashlib.sha256(url.encode("utf-8")).hexdigest())


def http_get(url, retries=3):
    return http_get_bytes(url, retries).decode("utf-8")


def http_get_bytes(url, retries=3):
    """The cache keeps the Last-Modified header next to the data, in <hash>.last-modified."""
    path = cache_path(_cache_dir, url) if _cache_dir else None
    if path and os.path.exists(path):
        if os.path.exists(path + ".last-modified"):
            with open(path + ".last-modified", encoding="utf-8") as f:
                _last_modified[url] = f.read().strip()
        with open(path, "rb") as f:
            return f.read()
    data, modified = _fetch(url, retries)
    if modified:
        _last_modified[url] = modified
    if path:
        with open(path + ".tmp", "wb") as f:
            f.write(data)
        os.replace(path + ".tmp", path)
        if modified:
            with open(path + ".last-modified", "w", encoding="utf-8") as f:
                f.write(modified)
    return data


def _fetch(url, retries):
    headers = {"User-Agent": USER_AGENT}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = "Bearer " + token
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read(), resp.headers.get("Last-Modified")
        except urllib.error.HTTPError as e:
            if e.code == 404 or attempt == retries - 1:
                raise BuildError(f"{url}: HTTP {e.code}") from e
        except OSError as e:
            if attempt == retries - 1:
                raise BuildError(f"{url}: {e}") from e
        time.sleep(2 ** attempt)


def download_all(urls):
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        return dict(zip(urls, pool.map(http_get, urls)))


def fetch_checked(url, sha256_url=None):
    """Download url; if sha256_url is given, verify the checksum against its first word."""
    data = http_get_bytes(url)
    if sha256_url:
        want = http_get(sha256_url).split()[0].lower()
        got = hashlib.sha256(data).hexdigest()
        if got != want:
            raise BuildError(f"{url}: sha256 {got} != {want}")
    return data


def github_dir(repo, ref, path="", ext=".txt"):
    """List files of a directory in a GitHub repo; returns {name without ext, lower-cased: download_url}."""
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={ref}"
    items = json.loads(http_get(url))
    if not isinstance(items, list):
        raise BuildError(f"{url}: unexpected response")
    return {
        it["name"][: len(it["name"]) - len(ext)].lower(): it["download_url"]
        for it in items
        if it["type"] == "file" and it["name"].endswith(ext)
    }


def github_commit_date(repo, ref, path=""):
    """Date of the last commit on ref that touched path (the whole tree if path is empty)."""
    url = f"https://api.github.com/repos/{repo}/commits?sha={urllib.parse.quote(ref)}&per_page=1"
    if path:
        url += "&path=" + urllib.parse.quote(path)
    items = json.loads(http_get(url))
    if not items:
        return None
    return datetime.datetime.fromisoformat(items[0]["commit"]["committer"]["date"].replace("Z", "+00:00"))


def last_modified(url):
    """When the content at url last changed: the commit date for raw.githubusercontent.com,
    which sends no Last-Modified, else the Last-Modified header seen when url was downloaded."""
    m = RAW_GITHUB_RE.match(url)
    if m:
        return github_commit_date(*m.groups())
    value = _last_modified.get(url)
    return email.utils.parsedate_to_datetime(value) if value else None
