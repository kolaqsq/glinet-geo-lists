import concurrent.futures
import hashlib
import json
import os
import time
import urllib.error
import urllib.request

from .errors import BuildError

USER_AGENT = "glinet-geo-lists"

_cache_dir = None


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
    if not _cache_dir:
        return _fetch(url, retries)
    path = cache_path(_cache_dir, url)
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    data = _fetch(url, retries)
    with open(path + ".tmp", "wb") as f:
        f.write(data)
    os.replace(path + ".tmp", path)
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
                return resp.read()
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
        it["name"][: -len(ext)].lower(): it["download_url"]
        for it in items
        if it["type"] == "file" and it["name"].endswith(ext)
    }
