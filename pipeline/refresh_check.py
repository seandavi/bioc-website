"""Gate for ops/refresh-packages.sh: is freshly built package data safe to upload?

    python3 -m pipeline.refresh_check OLD NEW

OLD and NEW are data directories holding <release>/<repo>/packages.json: OLD
from the snapshot being replaced, NEW just built. Every release in OLD is
checked, per repository. Exits non-zero, listing why, when NEW has more than
MAX_DROP fewer packages, or a record lacks a field the landing pages need.
Both are how an input that moved or came back empty shows up
(bioc-infrastructure#103): the pipeline writes the records without it rather
than failing.
"""

import json
import os
import re
import sys

from .since import REPOS, version_key

MAX_DROP = 0.02
FIELDS = ("since", "DownloadRank", "releases")


def load(data_dir, version, repo):
    with open(os.path.join(data_dir, version, repo, "packages.json"), encoding="utf-8") as fh:
        return json.load(fh)


def problems(old, new):
    """Why NEW must not replace OLD, one line each; empty when it may. Prints counts."""
    out = []
    versions = sorted((d for d in os.listdir(old) if re.fullmatch(r"\d+\.\d+", d)), key=version_key)
    for v in versions:
        for repo in REPOS:
            a, b = load(old, v, repo), load(new, v, repo)
            print(f"  {v} {repo:<16} {len(a):>5} -> {len(b):>5}", file=sys.stderr)
            if len(b) < (1 - MAX_DROP) * len(a):
                out.append(f"{v}/{repo}: {len(a)} -> {len(b)} packages, "
                           f"more than {MAX_DROP:.0%} fewer")
            for field in FIELDS:
                if n := sum(field not in rec for rec in b.values()):
                    out.append(f"{v}/{repo}: {n} of {len(b)} records without {field}")
    return out


def main(argv=None):
    old, new = argv or sys.argv[1:]
    print(f"package counts, {old} -> {new}:", file=sys.stderr)
    if bad := problems(old, new):
        print("REFUSING TO UPLOAD:\n  " + "\n  ".join(bad), file=sys.stderr)
        return 1
    print("package data checks passed", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
