"""How much of bioconductor.org does the Astro build actually reproduce?

Two directions, because either alone is misleading:

  precision  every URL we emit should exist upstream. Inventing URLs is worse
             than omitting them -- a 200 on a page the real site does not have
             is a silent wrong answer rather than a visible gap.
  recall     every URL upstream has should be emitted. Measured against the
             page inventories we can enumerate from primary sources, not
             against a crawl, since there is no sitemap to crawl from.

Recall is deliberately reported per page *type* rather than as one number. A
single percentage over a corpus that is 99% package pages would read as ~100%
while every prose page was missing.
"""

import json
import os
import random
import sys

from . import net

DIST = os.path.join("astro", "dist")
SITE = "https://bioconductor.org"


def built_urls():
    """Every path the build emitted, as site-absolute URLs."""
    out = set()
    for dirpath, _, filenames in os.walk(DIST):
        for fn in filenames:
            rel = os.path.relpath(os.path.join(dirpath, fn), DIST).replace(os.sep, "/")
            out.add("/" + rel)
    return out


def classify(url):
    if url.startswith("/packages/"):
        if url.endswith("/BiocViews.html"):
            return "biocViews browser"
        if url.endswith("/index.html"):
            return "package index"
        if "/html/" in url:
            return "package landing page"
        return "packages (other)"
    for prefix, name in (("/style/", "stylesheet"), ("/js/", "script"),
                         ("/images/", "image")):
        if url.startswith(prefix):
            return name
    return "prose page"


def expected():
    """Page inventories, from the same primary sources the build reads."""
    exp = {"package landing page": set(), "package index": set(),
           "biocViews browser": set(), "prose page": set()}
    data = os.path.join("astro", "data")
    for version in sorted(os.listdir(data)):
        vdir = os.path.join(data, version)
        if not os.path.isdir(vdir) or version == "site":
            continue
        for repo in ("bioc", "data/annotation", "data/experiment", "workflows"):
            f = os.path.join(vdir, repo, "packages.json")
            if not os.path.exists(f):
                continue
            with open(f) as fh:
                pkgs = json.load(fh)
            exp["package index"].add("/packages/%s/%s/index.html" % (version, repo))
            for name in pkgs:
                exp["package landing page"].add(
                    "/packages/%s/%s/html/%s.html" % (version, repo, name))
        if os.path.exists(os.path.join(vdir, "tree.json")):
            exp["biocViews browser"].add("/packages/%s/BiocViews.html" % version)

    pages = os.path.join(data, "site", "pages.json")
    if os.path.exists(pages):
        with open(pages) as fh:
            for p in json.load(fh):
                url = p["url"]
                exp["prose page"].add(
                    "/index.html" if url == "/" else url + "index.html")
    return exp


def check_upstream(urls, n, verbose=False):
    """Sample n URLs and confirm the real site serves them. Precision check."""
    sample = sorted(urls)
    random.Random(0).shuffle(sample)          # deterministic: reruns are comparable
    sample = sample[:n]

    def probe(u):
        # Directory-style URLs are what the site publishes; index.html resolves
        # to the same object but is not always the canonical form upstream.
        path = u[: -len("index.html")] if u.endswith("/index.html") else u
        try:
            net.fetch_bytes(SITE + path, retries=0, timeout=30)
            return (u, True)
        except Exception:
            return (u, False)

    got = [r for r in net.parallel(probe, sample, workers=8) if r]
    bad = [u for u, ok in got if not ok]
    if verbose and bad:
        for u in bad[:10]:
            print("      404 upstream: %s" % u, file=sys.stderr)
    return len(got), len(bad), bad


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="bioc coverage")
    ap.add_argument("--sample", type=int, default=40,
                    help="URLs per page type to verify against the live site")
    ap.add_argument("--no-network", action="store_true",
                    help="skip the upstream precision check")
    args = ap.parse_args(argv)

    if not os.path.isdir(DIST):
        raise SystemExit("no build at %s -- run `just build` first" % DIST)

    built = built_urls()
    exp = expected()
    by_type = {}
    for u in built:
        by_type.setdefault(classify(u), set()).add(u)

    print("\nBUILD OUTPUT")
    print("  %-24s %9s" % ("page type", "built"))
    for k in sorted(by_type, key=lambda k: -len(by_type[k])):
        print("  %-24s %9d" % (k, len(by_type[k])))
    print("  %-24s %9d" % ("TOTAL", len(built)))

    print("\nRECALL  (of what we can enumerate from primary sources)")
    print("  %-24s %9s %9s %9s" % ("page type", "expected", "built", "missing"))
    for k in sorted(exp):
        want, have = exp[k], by_type.get(k, set())
        missing = want - have
        pct = 100.0 * len(want & have) / len(want) if want else 100.0
        print("  %-24s %9d %9d %9d   %.1f%%"
              % (k, len(want), len(want & have), len(missing), pct))
        for m in sorted(missing)[:3]:
            print("      missing: %s" % m)

    if not args.no_network:
        print("\nPRECISION  (sampled URLs that must exist on bioconductor.org)")
        print("  %-24s %9s %9s" % ("page type", "checked", "not found"))
        for k in sorted(exp):
            have = by_type.get(k, set())
            if not have:
                continue
            n, bad, examples = check_upstream(have, args.sample)
            print("  %-24s %9d %9d   %s" % (k, n, bad,
                  "" if not bad else examples[0]))
    return 0
