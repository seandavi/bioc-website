# Astro parity build (spike)

A parallel implementation of the package landing pages, consuming the **same**
`packages.json` contract as the Nanoc build. The point is to prove the data seam
is renderer-agnostic, not to replace the site yet.

## Setup

    mkdir -p data
    for V in 3.23 3.24; do
      curl -s -o data/$V/tree.json --create-dirs \
        https://bioconductor.org/packages/json/$V/tree.json
      for R in bioc data/annotation data/experiment workflows; do
        curl -s -o "data/$V/$R/packages.json" --create-dirs \
          "https://bioconductor.org/packages/json/$V/$R/packages.json"
      done
    done
    npm install && npm run build

## Status (2026-08-03)

Builds **92,162 package landing pages across 35 releases (2.5 - 3.24) in 33 s**.
Integrity checked: the page count matches the packages.json record count exactly
for every version and repository, zero mismatches. Sampled URLs all resolve on
the live site.

Versions and repositories are discovered from `data/`, not hardcoded — the set
genuinely varies. JSON exists only from 2.5 onward (1.8-2.4 predate it), and
`workflows` first appears at 3.7.

For 3.23 alone the output was previously compared path-by-path against the Nanoc
build: 7,614 identical paths, zero spurious ones.

Not implemented: the 12 index / BiocViews pages, badges, site chrome and
navigation, and cross-repo dependency link resolution (links currently stay
within the same version+repo). Page bodies are therefore smaller than Nanoc's,
so the timing is a lower bound, not a like-for-like comparison.

## Next-gen pages (2026-08-11)

`/next/` renders from the **bioc-registry data plane** (propagation gate over
r-universe builds) instead of the legacy docroot — see `src/lib/prop.js`:

- `/next/{universe}/checkResults.html` — check matrix from the latest
  observation's `_jobs`, worst-first, with a propagated-version column. New
  work, not a port: nanoc never built check pages.
- `/next/{universe}/package/{pkg}.html` — one landing page per package the
  gate propagated, rendered through the **same PackageDetail component** as
  the parity build via `toContractRecord()` — the contract is source-agnostic.
  Version truth is the prop index; downloads are the gate's content-addressed
  artifacts.

Data is fetched at build time from the bioc-registry Worker (`PROP_DATA_BASE` to
override). Metadata comes from r-universe directly as a stopgap until the data
plane publishes a metadata artifact (issue #78); version skew between the live
build and the propagated version is surfaced in the page banner.
