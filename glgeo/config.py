"""Load config.json and check it before anything is downloaded.

Every key is checked against a schema: an unknown key (a typo such as "min_line") or a value
of the wrong type fails the build. Defaults live here and are filled in, so the rest of the
code reads cfg[...] directly.
"""

import json
import os
import re

from .errors import BuildError

REQUIRED = object()
NUMBER = "number"

OPTIONS = {
    "allow_tld": (bool, False),
    "max_shrink": (NUMBER, 0.5),
    "shrink_min_lines": (int, 100),
    # GL.iNet limits measured on MT6000, firmware 4.11.0
    "router_max_lines": (int, 200000),
    "router_max_ips": (int, 55000),
}
SOURCE_COMMON = {"name": (str, REQUIRED), "type": (str, REQUIRED), "min_lists": (int, 1)}
PRESET = {"include": (list, REQUIRED), "min_lines": (int, 1), "aggregate_ips": (bool, False), "description": (str, "")}
SOURCE_KINDS = ("geosite", "geoip")
PRESET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError) as e:
        raise BuildError(f"{path}: {e}") from e
    errors = []
    cfg = validate(raw, os.path.dirname(os.path.abspath(path)), errors)
    if errors:
        raise BuildError(f"{path}: invalid config:\n  " + "\n  ".join(errors))
    return cfg


def validate(raw, base_dir, errors):
    """Returns the config with defaults filled in; problems are appended to errors."""
    from . import presets, sources  # these import REQUIRED from here

    top = _section(raw, "", {"options": (dict, {}), "sources": (dict, REQUIRED), "presets": (dict, {})}, errors)
    opts = _section(top.get("options", {}), "options", OPTIONS, errors)
    if not 0 <= opts.get("max_shrink", 0) <= 1:
        errors.append("options.max_shrink: must be between 0 and 1")

    srcs = _section(top.get("sources", {}), "sources", {k: (list, []) for k in SOURCE_KINDS}, errors)
    for kind in SOURCE_KINDS:
        checked = []
        for i, src in enumerate(srcs.get(kind, [])):
            where = f"sources.{kind}[{i}]"
            mod = sources.REGISTRY.get(src.get("type")) if isinstance(src, dict) else None
            if isinstance(src, dict) and src.get("type") is not None and mod is None:
                errors.append(f"{where}.type: unknown type {src['type']!r}, known: {', '.join(sources.REGISTRY)}")
            elif mod and kind not in mod.KINDS:
                errors.append(f"{where}.type: {src['type']!r} cannot be used for {kind}")
            checked.append(_section(src, where, {**SOURCE_COMMON, **(mod.KEYS if mod else {})}, errors))
        srcs[kind] = checked

    out_presets = {}
    for name, preset in top.get("presets", {}).items():
        where = f"presets.{name}"
        if not PRESET_NAME_RE.match(name):
            errors.append(f"{where}: name must match {PRESET_NAME_RE.pattern} (it becomes a file name)")
        p = _section(preset, where, PRESET, errors)
        include = p.get("include", [])
        if isinstance(include, list) and not include:
            errors.append(f"{where}.include: empty")
        for j, item in enumerate(include if isinstance(include, list) else []):
            err = presets.check_include(item, base_dir)
            if err:
                errors.append(f"{where}.include[{j}]: {err}")
        out_presets[name] = p

    return {"options": opts, "sources": srcs, "presets": out_presets}


def _section(value, where, schema, errors):
    if not isinstance(value, dict):
        errors.append(f"{where or 'config'}: must be an object")
        return {}
    out = {}
    for key in value:
        if key not in schema:
            errors.append(f"{_join(where, key)}: unknown key, expected one of: {', '.join(schema)}")
    for key, (typ, default) in schema.items():
        if key in value:
            if _type_ok(value[key], typ):
                out[key] = value[key]
                if typ in (int, NUMBER) and value[key] < 0:
                    errors.append(f"{_join(where, key)}: must not be negative")
            else:
                errors.append(f"{_join(where, key)}: expected {_type_name(typ)}, got {json.dumps(value[key])}")
        elif default is REQUIRED:
            errors.append(f"{_join(where, key)}: required")
        else:
            out[key] = default
    return out


def _type_ok(value, typ):
    if typ is NUMBER:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if typ is int:
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, typ)


def _type_name(typ):
    if typ is NUMBER:
        return "a number"
    return {bool: "true/false", int: "an integer", str: "a string", list: "an array", dict: "an object"}[typ]


def _join(where, key):
    return f"{where}.{key}" if where else key
