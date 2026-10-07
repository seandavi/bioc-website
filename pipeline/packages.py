#!/usr/bin/env python3
"""Generate packages.json from real origins instead of from bioconductor.org.

The site build historically fetched VIEWS from the site it produces, converted it
to packages.json, and rendered ~7,600 package pages from that. This builds the
same packages.json, but sources each field from where the data actually
originates, and reports that provenance rather than hiding it.

Origins, per repository:

  bioc (software)              r-universe  — a genuine origin, no Bioconductor
                                             host involved
  data/annotation              ) DESCRIPTION read out of each source tarball.
  data/experiment              ) The maintainer's own file, passed through the
  workflows                    ) repository untouched. See pipeline/tarballs.py.
  reverse dependencies         computed across all four repos + CRAN PACKAGES
  DownloadRank                 bio-web-stats download scores (separate service;
                                             served under the site hostname but not
                                             site output), ranked within the repository

`--data-origin views` restores the old circular fetch of VIEWS off
bioconductor.org. It is kept only so the two can be compared; it cannot survive
the host being retired, which is the entire point of this pipeline.

One honest caveat about the tarball origin: VIEWS is a *superset* of the
repository. It lists packages that are registered for a release but whose
tarball never landed -- three workflow packages in 3.23 (SingscoreAMLMutations,
TCGAWorkflow, maEndToEnd) are in VIEWS with no file in src/contrib. Those get a
landing page today and will not get one from tarballs alone. Whether that is a
regression or a correction is a Bioconductor decision, not ours; it is recorded
in provenance.json rather than papered over.

Usage:
    python3 bioc.py packages --bioc 3.23 --out astro/data
    python3 bioc.py packages --bioc 3.23 --out astro/data --data-origin views
"""

import argparse, collections, json, os, re, sys, urllib.request

from . import net, since, tarballs

UA = {"User-Agent": "Mozilla/5.0 bioc-website/packages-json-generator"}
SITE = "https://bioconductor.org"
REPOS = ["bioc", "data/annotation", "data/experiment", "workflows"]

# clean_dcfs in scripts/get_json.rb converts exactly these to arrays.
ARRAY_FIELDS = {
    "Depends", "Suggests", "Imports", "Enhances", "biocViews", "LinkingTo",
    "vignettes", "vignetteTitles", "Rfiles", "dependsOnMe", "importsMe",
    "suggestsMe", "linksToMe",
}
# Confirmed unread by any template, helper or script. Not emitted.
UNUSED = {
    "MD5sum", "NeedsCompilation", "git_url", "git_last_commit",
    "git_last_commit_date", "Date/Publication", "VignetteBuilder", "OS_type",
    "License_is_FOSS", "License_restricts_use", "organism",
}
REV = {"Depends": "dependsOnMe", "Imports": "importsMe",
       "Suggests": "suggestsMe", "LinkingTo": "linksToMe"}

# The legacy build adds its repository's root biocViews term to every package,
# so a software package declaring only "DifferentialExpression" is published as
# ["DifferentialExpression", "Software"]. Packages do not declare it themselves
# -- it comes from which repository they were built into -- so a generator
# reading DESCRIPTION or r-universe has to add it back. Without this, biocViews
# differs from the published data on 89% of packages and the category browser
# loses its four top-level roots.
ROOT_TERM = {
    "bioc": "Software",
    "data/annotation": "AnnotationData",
    "data/experiment": "ExperimentData",
    "workflows": "Workflow",
}


def fetch(url, optional=False):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:
        if optional:
            print(f"  ! optional fetch failed {url}: {e}", file=sys.stderr)
            return None
        raise


def parse_dcf(text):
    recs, cur, key = [], {}, None
    for line in text.splitlines():
        if not line.strip():
            if cur:
                recs.append(cur); cur, key = {}, None
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_.@/-]*):\s?(.*)$", line)
        if m:
            key, cur[m.group(1)] = m.group(1), m.group(2)
        elif key:
            cur[key] += " " + line.strip()
    if cur:
        recs.append(cur)
    return {r["Package"]: r for r in recs if "Package" in r}


def split_list(v):
    return [x.strip() for x in re.split(r",\s*", v) if x.strip()] if v else []


def dep_name(entry):
    return re.split(r"[ (]", str(entry))[0]


# ---------------------------------------------------------------- origins ---

def from_runiverse(universe, branch):
    """Software packages, from r-universe. A real origin."""
    pkgs = json.loads(fetch(f"https://{universe}.r-universe.dev/api/packages"))
    out = {}
    for p in pkgs:
        name = p["Package"]
        rec = {"Package": name, "Version": p.get("Version")}
        for role in ("Depends", "Imports", "Suggests", "LinkingTo", "Enhances"):
            vals = [d["package"] + (f" ({d['version']})" if d.get("version") else "")
                    for d in (p.get("_dependencies") or []) if d.get("role") == role]
            if vals:
                rec[role] = vals
        for k in ("Title", "Description", "Author", "Maintainer", "License", "URL",
                  "BugReports", "SystemRequirements", "PackageStatus", "Video"):
            if p.get(k):
                # r-universe preserves DESCRIPTION's line breaks; VIEWS folds them.
                # Match VIEWS so rendered pages are byte-comparable.
                rec[k] = re.sub(r"\s+", " ", str(p[k])).strip()
        if p.get("biocViews"):
            rec["biocViews"] = split_list(p["biocViews"])
        # r-universe's own `Packaged` dates its rebuild (weeks to months after
        # Bioconductor's build), so use the date of the commit it built. Within
        # ~2 days before the tarball's `Packaged`.
        if updated := net.commit_date((p.get("_commit") or {}).get("time")):
            rec["Updated"] = updated
        rec["git_branch"] = branch
        if p.get("Version"):
            rec["source.ver"] = f"src/contrib/{name}_{p['Version']}.tar.gz"
        vigs = p.get("_vignettes") or []
        if vigs:
            rec["vignettes"] = [f"vignettes/{name}/inst/doc/{v['filename']}" for v in vigs]
            rec["vignetteTitles"] = [v.get("title", v["filename"]) for v in vigs]
        assets = p.get("_assets") or []
        rec["hasNEWS"] = any("NEWS" in a for a in assets)
        rec["hasREADME"] = bool(p.get("_readme"))
        out[name] = rec
    return out


def software_only(bioc, others):
    """The universes also hold experiment-data and workflow packages, which
    Bioconductor publishes in other repositories; a package belongs to exactly
    one repository, so r-universe records named in any other repository's set
    are not software. Packages that failed to build this cycle are in no
    PACKAGES index but are still kept (their landing pages must exist), unless
    another repository lists them: unserved workflows and data packages appear
    in that repository's VIEWS only, so `others` must include those names."""
    taken = set().union(*others)
    return {name: rec for name, rec in bioc.items() if name not in taken}


def from_views(version, repo, branch):
    """Fallback for repositories with no origin outside the site yet."""
    dcf = parse_dcf(fetch(f"{SITE}/packages/{version}/{repo}/VIEWS"))
    out = {}
    for name, r in dcf.items():
        rec = {}
        for k, v in r.items():
            if k in UNUSED:
                continue
            rec[k] = split_list(v) if k in ARRAY_FIELDS else v
        updated = net.packaged_date(rec.pop("Packaged", None))
        if updated:
            rec["Updated"] = updated
        for k in ("hasNEWS", "hasREADME", "hasINSTALL", "hasLICENSE"):
            if k in rec:
                rec[k] = str(rec[k]).strip().upper() == "TRUE"
        rec.setdefault("git_branch", branch)
        out[name] = rec
    return out


def rfiles_from_views(text):
    """{package: Rfiles} from a VIEWS file: the vignette R scripts the repository
    actually serves. r-universe has no equivalent, and the name can't be derived
    from the vignette (edgeR's Sweave User's Guide has no .R file)."""
    return {n: split_list(r["Rfiles"]) for n, r in parse_dcf(text).items() if r.get("Rfiles")}


def archived_packages(listing):
    """Package names in a src/contrib/Archive/ directory listing: the packages
    with older versions archived in this release (the legacy page HEADed
    Archive/<pkg>/ for each one)."""
    return set(re.findall(r'href="[^"]*/Archive/([^/"]+)/"', listing))


def repo_config(mirror=net.MIRROR):
    """The repository's own config.yaml: what BiocManager reads to map a
    Bioconductor version to its R version and to release/devel."""
    import yaml
    return yaml.safe_load(net.fetch(f"{mirror}/config.yaml")) or {}


def bin_dirs(rver):
    """packages.json field -> (binary directory, extension) for one R version.

    CRAN renamed the macOS arm64 directory at R 4.6 (big-sur-arm64 ->
    sonoma-arm64) and Bioconductor followed; Intel stayed put."""
    # ponytail: the renderer reads only the sonoma-arm64 field; releases on R < 4.6
    # are archival and never rebuilt, so their big-sur-arm64 field goes unread.
    arm = "sonoma-arm64" if tuple(int(x) for x in rver.split(".")) >= (4, 6) else "big-sur-arm64"
    return {
        "win.binary.ver": (f"bin/windows/contrib/{rver}", "zip"),
        f"mac.binary.{arm}.ver": (f"bin/macosx/{arm}/contrib/{rver}", "tgz"),
        "mac.binary.big-sur-x86_64.ver": (f"bin/macosx/{MAC_X86}/contrib/{rver}", "tgz"),
    }


MAC_X86 = "big-sur-x86_64"


def repo_index(repo, bioc, rver, mirror=net.MIRROR):
    """{field: {package: version}} from the repository's own PACKAGES indexes,
    source and binary. A missing binary index (data repositories have none) is
    an empty map, not an error."""
    base = f"{mirror}/packages/{bioc}/{repo}"
    idx = {"source.ver": {n: r["Version"] for n, r in parse_dcf(
        fetch(f"{base}/src/contrib/PACKAGES")).items() if r.get("Version")}}
    for field, (d, _) in bin_dirs(rver).items():
        txt = fetch(f"{base}/{d}/PACKAGES", optional=True)
        idx[field] = {n: r["Version"] for n, r in parse_dcf(txt).items() if r.get("Version")} if txt else {}
    return idx


def apply_downloads(pkgs, idx, rver):
    """Point every download link at a file the repository actually serves.

    Download links and the displayed Version come from the repository's PACKAGES
    indexes, never from the metadata origin: r-universe's latest successful build
    is not necessarily what Bioconductor propagated (43 release packages differed
    on 2026-09-29), and a link built from it is a 404. A binary is linked at its
    own version, which may trail the source (the build system keeps the last
    binary that built). Returns {package: metadata-origin version} for packages
    whose version was corrected, and the packages the repository doesn't serve."""
    corrected, unserved = {}, []
    dirs = bin_dirs(rver)
    for name, rec in pkgs.items():
        src = idx["source.ver"].get(name)
        if src is None:
            rec.pop("source.ver", None)
            unserved.append(name)
        else:
            if rec.get("Version") and rec["Version"] != src:
                corrected[name] = rec["Version"]
                # Updated dates the origin's build, not the version shown.
                rec.pop("Updated", None)
            rec["Version"] = src
            rec["source.ver"] = f"src/contrib/{name}_{src}.tar.gz"
        for field, (d, ext) in dirs.items():
            v = idx[field].get(name)
            if v:
                rec[field] = f"{d}/{name}_{v}.{ext}"
            else:
                rec.pop(field, None)
    return corrected, sorted(unserved)


def load_scores(repo):
    """Download scores are not package metadata and not site output — they come
    from bio-web-stats, a separate Flask/Postgres service fed by a daily Athena job
    over CloudFront logs. Confirmed live: /packages/stats/* answers with
    `Server: waitress` while every other path answers `Server: Apache/2.4.52`,
    so this is already decoupled from master and is a genuine origin. It is
    only *addressed* through the shared hostname — which means the routing for
    this path is a must-preserve item during any cutover.

    The file's second column is a score (distinct IPs over the last 12 months),
    not a rank; see rank_by_score().

    Note the directory and filename slugs differ for the data repositories."""
    dirslug, fileslug = {
        "bioc": ("bioc", "bioc"),
        "workflows": ("workflows", "workflows"),
        "data/annotation": ("data-annotation", "annotation"),
        "data/experiment": ("data-experiment", "experiment"),
    }[repo]
    txt = fetch(f"{SITE}/packages/stats/{dirslug}/{fileslug}_pkg_scores.tab", optional=True)
    if not txt:
        return {}
    scores = {}
    for line in txt.splitlines():
        if line.startswith("Package\t"):
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            try:
                scores[parts[0].strip()] = int(parts[1])
            except ValueError:
                pass
    return scores


def rank_by_score(scores, names):
    """{package: rank} within `names`: 1 is the most downloaded.

    Ties share the best rank of the group, and a package with no score ranks as
    zero, as in the legacy scripts/badge_generation.rb getRanking(). Scores for
    packages outside `names` (removed from the release) do not take a place."""
    ordered = sorted((scores.get(n, 0) for n in names), reverse=True)
    first = {}
    for i, score in enumerate(ordered, 1):
        first.setdefault(score, i)
    return {n: first[scores.get(n, 0)] for n in names}


# ------------------------------------------------------------------ build ---

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--bioc", default="3.23")
    ap.add_argument("--out", default="./out")
    ap.add_argument("--universe", default=None,
                    help="r-universe to read software metadata from; default: "
                         "'bioc' for the devel version in config.yaml, else 'bioc-release'")
    ap.add_argument("--software-origin", choices=["runiverse", "views"], default="runiverse")
    ap.add_argument("--data-origin", choices=["tarballs", "views"], default="tarballs",
                    help="origin for annotation/experiment/workflows metadata. "
                         "'tarballs' reads DESCRIPTION out of each source tarball "
                         "(a real origin); 'views' is the old circular fetch and "
                         "exists only for comparison.")
    args = ap.parse_args(argv)

    cfg = repo_config()
    if args.universe is None:
        args.universe = "bioc" if str(cfg.get("devel_version")) == args.bioc else "bioc-release"
    rver = str((cfg.get("r_ver_for_bioc_ver") or {}).get(args.bioc) or "")
    if not rver:
        sys.exit(f"config.yaml has no r_ver_for_bioc_ver for {args.bioc}")
    branch = "devel" if args.universe == "bioc" else "RELEASE_" + args.bioc.replace(".", "_")
    provenance, repos, tarball_reports = {}, {}, []

    for repo in REPOS:
        if repo == "bioc" and args.software_origin == "runiverse":
            print(f"[{repo}] origin: r-universe ({args.universe})", file=sys.stderr)
            repos[repo] = from_runiverse(args.universe, branch)
            provenance[repo] = f"r-universe:{args.universe}"
        elif args.data_origin == "tarballs":
            # DESCRIPTION inside the source tarball -- the maintainer's own file,
            # passed through the repository untouched. This is what replaced the
            # circular VIEWS fetch for the three repositories r-universe does not
            # cover. See pipeline/tarballs.py for why it is affordable.
            recs, rep = tarballs.describe_repo(repo, args.bioc, branch)

            # A minority of archives are not ordered with DESCRIPTION near the
            # front -- BSgenome.Hsapiens.UCSC.hg17 puts a multi-hundred-megabyte
            # chr13.rda first -- so no affordable prefix reaches it, and gzip
            # cannot be read backwards. Those fall back to VIEWS, which is still
            # circular. Naming them here keeps the residue visible instead of
            # letting a 96%-good origin read as a solved problem.
            if rep["missed"]:
                fallback = from_views(args.bioc, repo, branch)
                filled = [n for n in rep["missed"] if n in fallback]
                for n in filled:
                    recs[n] = fallback[n]
                rep["views_fallback"] = sorted(filled)
                rep["unresolved"] = sorted(set(rep["missed"]) - set(filled))
                print("  + %d filled from VIEWS (still circular), %d unresolved"
                      % (len(filled), len(rep["unresolved"])), file=sys.stderr)

            repos[repo] = recs
            provenance[repo] = "tarball DESCRIPTION %d/%d%s" % (
                rep["described"], rep["packages_in_index"],
                "; %d via VIEWS fallback" % len(rep.get("views_fallback", []))
                if rep.get("views_fallback") else "")
            tarball_reports.append(rep)
        else:
            why = "forced" if repo == "bioc" else "--data-origin views"
            print(f"[{repo}] origin: VIEWS  ({why})", file=sys.stderr)
            repos[repo] = from_views(args.bioc, repo, branch)
            provenance[repo] = "VIEWS (circular)"

    if args.software_origin == "runiverse":
        repos["bioc"] = software_only(
            repos["bioc"], [set(repos[r]) | set(from_views(args.bioc, r, branch)) for r in REPOS[1:]])
        # Optional: without it the pages just show no R Script links.
        if views := fetch(f"{SITE}/packages/{args.bioc}/bioc/VIEWS", optional=True):
            for name, rfiles in rfiles_from_views(views).items():
                if name in repos["bioc"]:
                    repos["bioc"][name]["Rfiles"] = rfiles

    # Source archives exist only for releases (devel has no Archive/) and only
    # for software, as on the legacy page. Optional: no field, no link.
    if str(cfg.get("devel_version")) != args.bioc:
        listing = fetch(f"{SITE}/packages/{args.bioc}/bioc/src/contrib/Archive/", optional=True)
        if listing:
            archived = archived_packages(listing)
            for name, rec in repos["bioc"].items():
                rec["hasArchive"] = name in archived

    # Reverse dependencies span every repository AND CRAN — a Bioconductor page
    # lists CRAN packages that depend on it. So the graph is built from all four
    # repos plus CRAN's own PACKAGES index, which is a genuine external origin.
    rev = collections.defaultdict(lambda: collections.defaultdict(set))
    for repo, pkgs in repos.items():
        for name, rec in pkgs.items():
            for role, field in REV.items():
                for d in rec.get(role, []):
                    rev[dep_name(d)][field].add(name)

    cran = fetch("https://cran.r-project.org/src/contrib/PACKAGES", optional=True)
    if cran:
        n = 0
        for name, rec in parse_dcf(cran).items():
            for role, field in REV.items():
                for d in split_list(rec.get(role, "")):
                    rev[dep_name(d)][field].add(name)
            n += 1
        print(f"folded {n} CRAN packages into the reverse-dependency graph", file=sys.stderr)

    downloads = {}
    for repo, pkgs in repos.items():
        corrected, unserved = apply_downloads(pkgs, repo_index(repo, args.bioc, rver), rver)
        downloads[repo] = {"version_corrected_from_origin": corrected, "not_in_repository": unserved}
        print(f"[{repo}] downloads from the repository's PACKAGES: {len(corrected)} versions "
              f"corrected, {len(unserved)} not in the repository", file=sys.stderr)

    # First release and release list per package, from the releases already on
    # disk. If any release from 2.5 up to this one is missing, "first seen" and
    # the list are wrong, so both fields are left out, loudly.
    first, seen, where = since.history(args.out, before=args.bioc)
    if gaps := since.missing(seen, cfg, args.bioc):
        print(f"  ! no data in {args.out} for releases {', '.join(gaps)}: 'since' and 'releases' omitted",
              file=sys.stderr)
        first = None
    else:
        records = {v: since.record(v, cfg) for v in set(first.values()) | {args.bioc}}

    total = 0
    for repo, pkgs in repos.items():
        scores = load_scores(repo)
        ranks = rank_by_score(scores, pkgs) if scores else {}
        for name, rec in pkgs.items():
            for field in REV.values():
                if rev[name][field]:
                    rec[field] = sorted(rev[name][field], key=str.lower)
            if name in ranks:
                rec["DownloadRank"] = ranks[name]
            # Repository root term -- see ROOT_TERM. Sorted so the order does not
            # depend on whether the package happened to declare it itself.
            root = ROOT_TERM.get(repo)
            if root:
                rec["biocViews"] = sorted(set(rec.get("biocViews", [])) | {root})
            if first is not None:
                rec["since"] = records[first.get(name, args.bioc)]
                rec["releases"] = since.releases(where.get(name, {}), args.bioc, repo)
            rec["dependencyCount"] = str(len({
                dep_name(d) for role in ("Depends", "Imports", "LinkingTo")
                for d in rec.get(role, []) if dep_name(d) != "R"
            }))
        d = os.path.join(args.out, args.bioc, repo)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "packages.json"), "w", encoding="utf-8") as fh:
            json.dump(pkgs, fh, indent=2, sort_keys=True)
        total += len(pkgs)
        print(f"  wrote {len(pkgs):>5} packages  {d}/packages.json", file=sys.stderr)

    print(f"\n{total} packages written under {args.out}/{args.bioc}", file=sys.stderr)
    print("\nprovenance:", file=sys.stderr)
    for repo, src in provenance.items():
        print(f"  {repo:<18} {src}", file=sys.stderr)
    print(f"  {'DownloadRank':<18} bio-web-stats (separate service, genuine origin)", file=sys.stderr)
    print(f"  {'reverse deps':<18} computed across all four repos + CRAN", file=sys.stderr)

    # Provenance is written next to the data, not just printed. A build that
    # silently fell back to a circular source must be detectable afterwards.
    meta = {"bioc_version": args.bioc, "branch": branch, "origins": provenance,
            "tarball_reports": tarball_reports, "r_version": rver, "downloads": downloads,
            "since": "omitted: no history" if first is None else "computed"}
    with open(os.path.join(args.out, args.bioc, "provenance.json"), "w") as fh:
        json.dump(meta, fh, indent=1)


if __name__ == "__main__":
    main()
