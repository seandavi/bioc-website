"""'In Bioconductor since' and the releases list: which releases each package is in.

For software, "since" is what the legacy site showed: the oldest release whose
branch of the manifest repo lists the package in software.txt (manifest_first).
The manifest starts at 1.6, so a package listed there is "1.6 or earlier".

The legacy site showed no "since" for the other repos. Theirs, and every
package's releases list, come from the per-release packages.json files already
under astro/data/. Those start at 2.5, so a package first seen there is "2.5 or
earlier". The R version and release date of a release come from the site's
config.yaml.
"""

import datetime
import json
import os
import re
import subprocess
import tempfile

EARLIEST = "2.5"
MANIFEST_EARLIEST = "1.6"
MANIFEST = "https://git.bioconductor.org/admin/manifest"
REPOS = ("bioc", "data/annotation", "data/experiment", "workflows")


def version_key(v):
    return tuple(int(x) for x in v.split("."))


def history(data_dir, before):
    """({package: first release}, releases older than `before`, {package: {release: repo}}).

    A release counts as on disk only if some repo's packages.json in it is
    non-empty. The repo map covers every release on disk except `before` itself
    (devel is newer than a release being rebuilt), so the version switcher sees it too."""
    first, where, populated = {}, {}, set()
    versions = sorted((d for d in os.listdir(data_dir)
                       if re.fullmatch(r"\d+\.\d+", d) and d != before), key=version_key)
    for v in versions:
        for repo in REPOS:
            f = os.path.join(data_dir, v, repo, "packages.json")
            if os.path.exists(f):
                with open(f, encoding="utf-8") as fh:
                    for name in json.load(fh):
                        populated.add(v)
                        where.setdefault(name, {})[v] = repo
                        if version_key(v) < version_key(before):
                            first.setdefault(name, v)
    return first, [v for v in versions if v in populated and version_key(v) < version_key(before)], where


def missing(seen, cfg, before):
    """Releases in config.yaml from EARLIEST up to `before` that are not in `seen`.

    "First seen" and the releases list are only right if no release in between
    is absent from disk."""
    return sorted((v for v in (cfg.get("r_ver_for_bioc_ver") or {})
                   if version_key(EARLIEST) <= version_key(v) < version_key(before) and v not in seen),
                  key=version_key)


def releases(where, version, repo):
    """The `releases` field: [release, repo] for every release the package is in, newest first.

    `repo` is the URL-path segment of /packages/<release>/<repo>/html/<name>.html,
    so a package that moved between repos lists the repo it had at the time."""
    merged = {**where, version: repo}
    return [[v, merged[v]] for v in sorted(merged, key=version_key, reverse=True)]


def manifest_lists(cfg, url=MANIFEST):
    """{release: software.txt} for every release in config.yaml's release_dates
    plus devel, read from one shallow clone of the manifest repo. A release
    with no branch (before 1.6) is left out, as the legacy Rules file did."""
    devel = str(cfg.get("devel_version"))
    branches = {v: "devel" if v == devel else "RELEASE_" + v.replace(".", "_")
                for v in [*(cfg.get("release_dates") or {}), devel]}
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "clone", "-q", "--bare", "--depth", "1", "--no-single-branch", url, d],
                       check=True)
        out = {}
        for v, branch in branches.items():
            r = subprocess.run(["git", "-C", d, "show", f"{branch}:software.txt"],
                               capture_output=True, text=True)
            if r.returncode == 0:
                out[v] = r.stdout
        return out


def manifest_first(lists):
    """{package: oldest release whose software.txt lists it} from manifest_lists()."""
    first = {}
    for v in sorted(lists, key=version_key):
        for line in lists[v].splitlines():
            if line.startswith("Package: "):
                first.setdefault(line[len("Package: "):].strip(), v)
    return first


def record(version, cfg, earliest=EARLIEST):
    """The `since` field for a package first seen in `version`; `earliest` is
    the oldest release of the history it was read from.

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
    if version == earliest:
        rec["orEarlier"] = True
    return rec
