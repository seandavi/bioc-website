"""'In Bioconductor since': the first release each package appears in.

The history is the per-release packages.json files already under astro/data/;
the R version and release date of that release come from the site's config.yaml.
Data starts at 2.5 (JSON exists from there), so a package first seen then is
"2.5 or earlier", not "2.5".
"""

import datetime
import json
import os
import re

EARLIEST = "2.5"


def version_key(v):
    return tuple(int(x) for x in v.split("."))


def history(data_dir, before):
    """({package: first release}, releases read): the releases on disk older than `before`."""
    first = {}
    versions = sorted((d for d in os.listdir(data_dir)
                       if re.fullmatch(r"\d+\.\d+", d) and version_key(d) < version_key(before)),
                      key=version_key)
    for v in versions:
        for repo in ("bioc", "data/annotation", "data/experiment", "workflows"):
            f = os.path.join(data_dir, v, repo, "packages.json")
            if os.path.exists(f):
                with open(f, encoding="utf-8") as fh:
                    for name in json.load(fh):
                        first.setdefault(name, v)
    return first, versions


def record(version, cfg):
    """The `since` field for a package first seen in `version`.

    No R version is an error. No release date is an error too, except for the
    devel version, which has not been released yet."""
    rver = (cfg.get("r_ver_for_bioc_ver") or {}).get(version)
    if not rver:
        raise SystemExit(f"config.yaml has no r_ver_for_bioc_ver for {version}")
    rec = {"release": version, "r": str(rver)}
    date = (cfg.get("release_dates") or {}).get(version)
    if date:
        rec["date"] = datetime.datetime.strptime(date, "%m/%d/%Y").date().isoformat()
    elif version != str(cfg.get("devel_version")):
        raise SystemExit(f"config.yaml has no release_dates for {version}")
    if version == EARLIEST:
        rec["orEarlier"] = True
    return rec
