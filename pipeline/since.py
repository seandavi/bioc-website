"""'In Bioconductor since' and the releases list: which releases each package is in.

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
REPOS = ("bioc", "data/annotation", "data/experiment", "workflows")


def version_key(v):
    return tuple(int(x) for x in v.split("."))


def history(data_dir, before):
    """({package: first release}, releases older than `before`, {package: {release: repo}}).

    The repo map covers every release on disk except `before` itself (devel is
    newer than a release being rebuilt), so the version switcher sees it too."""
    first, where = {}, {}
    versions = sorted((d for d in os.listdir(data_dir)
                       if re.fullmatch(r"\d+\.\d+", d) and d != before), key=version_key)
    for v in versions:
        for repo in REPOS:
            f = os.path.join(data_dir, v, repo, "packages.json")
            if os.path.exists(f):
                with open(f, encoding="utf-8") as fh:
                    for name in json.load(fh):
                        where.setdefault(name, {})[v] = repo
                        if version_key(v) < version_key(before):
                            first.setdefault(name, v)
    return first, [v for v in versions if version_key(v) < version_key(before)], where


def releases(where, version, repo):
    """The `releases` field: [release, repo] for every release the package is in, newest first.

    `repo` is the URL-path segment of /packages/<release>/<repo>/html/<name>.html,
    so a package that moved between repos lists the repo it had at the time."""
    merged = {**where, version: repo}
    return [[v, merged[v]] for v in sorted(merged, key=version_key, reverse=True)]


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
