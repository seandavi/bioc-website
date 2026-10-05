"""Package metadata from the source tarballs, for the repositories r-universe
does not cover.

This closes the largest hole in the provenance story. r-universe has universes
for Bioconductor *software* only; annotation, experiment and workflow packages
-- about 1,392 packages, a third of the corpus -- had no origin outside the site
being rebuilt, so `packages.json` for them was made by parsing VIEWS off
bioconductor.org. That is circular: it cannot survive the host being retired.

`DESCRIPTION` inside the source tarball is the real origin. It is the
maintainer's own file, passed through the repository untouched, and it carries
every field VIEWS carries plus the git provenance stamped in at build time.

The trick that makes this affordable
------------------------------------
A naive implementation downloads 1,392 tarballs. Annotation packages are huge --
several are hundreds of megabytes -- so that is hundreds of gigabytes to read a
few hundred bytes from each.

Instead: `DESCRIPTION` is written near the front of the archive, gzip is a
stream, and R2 serves ranged requests. So fetch only the first 64 KB, inflate as
much of the gzip stream as that yields (typically ~200 KB of tar), and walk the
512-byte tar headers to find `<pkg>/DESCRIPTION`. Measured at roughly 0.1-0.2 s
per package and a bounded 64 KB regardless of how large the package is.

The cost of that trick is that we see only the front of the archive, so the
whole-archive facts -- hasNEWS/hasREADME/hasINSTALL/hasLICENSE, the vignette
list, Rfiles -- are NOT recoverable this way. They are reported as unavailable
rather than guessed; see `describe_repo`'s return value. Guessing them False
would silently drop the documentation links from ~1,400 landing pages, which is
exactly the class of "green build measuring the wrong thing" this project keeps
hitting.
"""

import re
import sys
import zlib

from . import net

# 64 KB inflates to roughly 200 KB of tar for a typical package, which covers
# the first few dozen members. Packages whose DESCRIPTION falls outside that get
# one retry at 512 KB before being given up on -- see describe().
PREFIX_BYTES = 65536
PREFIX_RETRY_BYTES = 524288


def tar_members(raw):
    """Walk 512-byte ustar headers over a possibly-truncated tar stream.

    Yields (name, size, data_offset). Stops cleanly at the first short or
    zero header, which is the normal end of what a prefix gives us.
    """
    out, off = [], 0
    while off + 512 <= len(raw):
        hdr = raw[off:off + 512]
        if hdr[:1] == b"\0":
            break
        name = hdr[0:100].split(b"\0")[0].decode("utf-8", "replace")
        try:
            size = int(hdr[124:136].split(b"\0")[0].strip() or b"0", 8)
        except ValueError:
            break
        out.append((name, size, off + 512))
        off += 512 + (size + 511) // 512 * 512
    return out


def _inflate_prefix(blob):
    """Inflate as much of a truncated gzip stream as possible.

    zlib raises when the stream ends mid-block; that is expected here and the
    bytes decoded before the error are still valid, so they are kept.
    """
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        return d.decompress(blob)
    except zlib.error:
        return b""


def describe(pkg, version, repo, bioc, mirror=net.MIRROR, nbytes=PREFIX_BYTES):
    """Return the parsed DESCRIPTION for one package, or None."""
    url = "%s/packages/%s/%s/src/contrib/%s_%s.tar.gz" % (mirror, bioc, repo, pkg, version)
    blob = net.fetch_range(url, nbytes, optional=True)
    if not blob:
        return None
    raw = _inflate_prefix(blob)
    if not raw:
        return None
    for name, size, off in tar_members(raw):
        if name.endswith("/DESCRIPTION") and name.count("/") == 1:
            body = raw[off:off + size]
            # A truncated prefix can cut DESCRIPTION itself in half. Parsing that
            # yields a record missing arbitrary trailing fields -- silently wrong
            # rather than loudly broken -- so require the whole member.
            if len(body) < size:
                break
            recs = net.parse_dcf(body.decode("utf-8", "replace"))
            return recs.get(pkg) or (list(recs.values())[0] if recs else None)
    # DESCRIPTION was past the window (or split across it). One wider retry.
    if nbytes < PREFIX_RETRY_BYTES:
        return describe(pkg, version, repo, bioc, mirror, PREFIX_RETRY_BYTES)
    return None


def versions_from_packages(repo, bioc, mirror=net.MIRROR):
    """{package: version} from the repository's own PACKAGES index.

    PACKAGES is a genuine repository artifact -- it is what `install.packages()`
    reads -- and it gives the exact tarball filenames without needing a
    directory listing, which R2 does not serve.
    """
    txt = net.fetch("%s/packages/%s/%s/src/contrib/PACKAGES" % (mirror, bioc, repo))
    return {name: r.get("Version") for name, r in net.parse_dcf(txt).items() if r.get("Version")}


# Fields present in DESCRIPTION that no page reads, or that VIEWS never carried.
# Dropped so the output stays comparable to the existing packages.json contract.
DROP = {
    "MD5sum", "NeedsCompilation", "Repository", "Date/Publication",
    "VignetteBuilder", "OS_type", "License_is_FOSS", "License_restricts_use",
    "organism", "Encoding", "RoxygenNote", "Date", "Authors@R", "LazyLoad",
    "LazyData", "Collate", "ByteCompile", "biocViewsVocab", "git_url",
    "git_last_commit", "git_last_commit_date", "Type", "Config/testthat/edition",
}
ARRAY_FIELDS = {"Depends", "Suggests", "Imports", "Enhances", "LinkingTo", "biocViews"}


def to_record(dcf, branch):
    """DESCRIPTION fields -> the packages.json record shape.

    Scalar text is whitespace-collapsed. DESCRIPTION wraps prose across lines and
    a wrapped line may end in a space, so naive unfolding yields a double space
    where VIEWS has one. Left alone this shows up as a diff on 8 of 25 workflow
    packages -- cosmetic, but enough to make a byte-comparison gate useless.
    """
    rec = {}
    for k, v in dcf.items():
        if k in DROP:
            continue
        rec[k] = net.split_list(v) if k in ARRAY_FIELDS else re.sub(r"\s+", " ", v).strip()
    packaged = net.packaged_date(rec.pop("Packaged", None))
    if packaged:
        rec["Packaged"] = packaged
    rec["git_branch"] = branch
    if rec.get("Version"):
        rec["source.ver"] = "src/contrib/%s_%s.tar.gz" % (rec["Package"], rec["Version"])
    return rec


def describe_repo(repo, bioc, branch, mirror=net.MIRROR, workers=12):
    """Every package in one repository, from its tarballs.

    Returns (records, report). `report` carries the misses explicitly -- a
    silent shortfall here would show up as missing landing pages much later.
    """
    versions = versions_from_packages(repo, bioc, mirror)
    names = sorted(versions)
    print("[%s] %d packages in PACKAGES; reading DESCRIPTION from tarball prefixes"
          % (repo, len(names)), file=sys.stderr)

    got = net.parallel(
        lambda n: describe(n, versions[n], repo, bioc, mirror),
        names, workers=workers, label="%s DESCRIPTION" % repo)

    out, missed = {}, []
    for name, dcf in zip(names, got):
        if dcf is None:
            missed.append(name)
            continue
        out[name] = to_record(dcf, branch)

    report = {
        "repo": repo,
        "packages_in_index": len(names),
        "described": len(out),
        "missed": missed,
        # Stated, not guessed. These need the whole archive; the prefix cannot
        # see them, and no consumer should read them as "known false".
        "unavailable_fields": ["hasNEWS", "hasREADME", "hasINSTALL", "hasLICENSE",
                               "vignettes", "vignetteTitles", "Rfiles"],
    }
    if missed:
        print("  ! %d/%d not described: %s%s" % (
            len(missed), len(names), ", ".join(missed[:8]),
            " ..." if len(missed) > 8 else ""), file=sys.stderr)
    return out, report
