import json
import os
import shutil
import time

SUBDIRS = ("geosite", "geoip", "geoip6", "presets")


def clean(out_dir):
    for sub in SUBDIRS:
        shutil.rmtree(os.path.join(out_dir, sub), ignore_errors=True)


def write_list(out_dir, rel, lines, index):
    path = os.path.join(out_dir, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(line + "\n" for line in lines))
    index[rel] = len(lines)


def write_index(out_dir, index):
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "files": index},
                  f, indent=1, sort_keys=True)
