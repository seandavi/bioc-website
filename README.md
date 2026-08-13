# bioconductor-website

The next-generation [bioconductor.org](https://bioconductor.org) site: a static
Astro build fed by a small Python pipeline, replacing the legacy nanoc site.

Two halves, one seam — `astro/data/` is the contract between them:

| half | does | lives in |
|---|---|---|
| pipeline | fetches from primary sources into `astro/data/` | `pipeline/`, driven by `./bioc.py` |
| renderer | turns `astro/data/` into a static site | `astro/` |

The pipeline reads only public sources: the
[Bioconductor/bioconductor.org](https://github.com/Bioconductor/bioconductor.org)
git repo (prose pages, assets), [r-universe](https://bioc.r-universe.dev)
(package metadata), package tarballs (DESCRIPTION via ranged reads), and the
biocViews vocabulary. The `/next/` pages additionally read build/check/propagation
state from the bioc-prop data plane (see `astro/src/lib/prop.js`).

## Quickstart

```sh
just install        # npm install in astro/
just data           # fetch everything into astro/data/ (releases 3.23,3.24)
just build          # astro/dist/
just dev            # dev server on :4321
```

`just --list` shows the finer-grained recipes (content only, one release's
packages.json, etc.). `astro/README.md` has renderer details and a
pipeline-free curl setup for the parity pages.

## Status

- Parity track: package landing pages, repo indexes, and biocViews browsers for
  releases 2.5–3.24; prose pages from the site git repo. Coverage is measured
  (`just coverage`), not assumed.
- `/next/` track: check-results and package pages rendered from the propagation
  data plane. New work — the legacy site never built check pages.
- Not here yet: CI build + PR previews, publish-to-R2 deploy, and the one-time
  markdown import of prose content (after which content changes by PR in this
  repo).

This repo was extracted (fresh history, 2026-08) from the private
bioconductor.org-migration repo; serving infrastructure, sync tooling, and
migration runbooks remain there.
