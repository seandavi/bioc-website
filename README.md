# bioc-website

[![site](https://github.com/seandavi/bioc-website/actions/workflows/site.yml/badge.svg)](https://github.com/seandavi/bioc-website/actions/workflows/site.yml)

The next-generation [bioconductor.org](https://bioconductor.org) site: a static
Astro build fed by a small Python pipeline, replacing the legacy nanoc site.

For why this exists, what it replaces, and where it stands, see
[docs/OVERVIEW.md](docs/OVERVIEW.md).

Two halves, one seam — `astro/data/` is the contract between them:

| half | does | lives in |
|---|---|---|
| pipeline | fetches from primary sources into `astro/data/` | `pipeline/`, driven by `./bioc.py` |
| renderer | turns `astro/data/` into a static site | `astro/` |

Nothing downstream of `astro/data/` knows where the data came from, and nothing
upstream knows how it is rendered. That seam is what let the same
`PackageDetail` component render both the legacy-parity pages and the
data-plane-fed `/next/` pages unchanged.

## How the site is built

```mermaid
flowchart LR
  subgraph sources ["primary sources (all public)"]
    nanoc["Bioconductor/bioconductor.org<br/>prose pages, assets"]
    runi["r-universe<br/>package metadata"]
    tarballs["package tarballs<br/>DESCRIPTION via ranged reads"]
    views["biocViews vocabulary"]
  end
  subgraph repo ["this repo"]
    pipeline["pipeline/ + bioc.py"]
    data[("astro/data/<br/>the contract")]
    astro["astro/ renderer"]
    dist["astro/dist/<br/>~97k pages, ~60 s"]
  end
  prop["bioc-registry data plane<br/>build/check/propagation state"]
  nanoc & runi & tarballs & views --> pipeline --> data --> astro --> dist
  prop -- "build-time fetch (/next/ pages)" --> astro
```

The parity track rebuilds the legacy site's package landing pages, repository
indexes, and biocViews browsers for releases 2.5–3.24, plus the prose pages,
from primary sources — no access to the legacy hosts required. Coverage
against the live site is measured (`just coverage`), not assumed. The `/next/`
track renders check-results and package pages from the
[bioc-registry data plane](https://bioc-registry.seandavi.workers.dev/docs) — new
work; the legacy site never built check pages.

## How builds are published and served

```mermaid
flowchart LR
  pr["pull request"] -- "CI build" --> preview["R2: preview/pr-&lt;n&gt;/<br/>deleted on close"]
  main["push to main"] -- "CI build" --> site["R2: site/&lt;sha&gt;/ (immutable)<br/>+ site/latest pointer"]
  snapshot["R2: _ci/site-data.tar.zst<br/>data snapshot"] -. "pulled by CI<br/>instead of refetching sources" .-> pr & main
  worker["Cloudflare Worker<br/>(private infra repo)"] --> preview & site
  worker --> legacy["mirrored legacy content<br/>(everything not yet ported)"]
  visitor(("visitor")) --> worker
```

The split is deliberate: **this repo publishes builds; the Worker decides what
is served.** Write access here never implies the power to change production —
that lives with the route table in the private infra repo, where deploy is a
pointer move and rollback is moving it back.

Concretely (`.github/workflows/site.yml`):

- **Every PR** is built and published to `preview/pr-<n>/`, served at
  `https://bioc-dev.cancerdatasci.org/_pr/<n>/`. The URL is posted as a sticky
  PR comment, the prefix is overwritten on every push, and
  `preview-cleanup.yml` deletes it when the PR closes. Preview pages are
  served `no-cache`. (Internal links are root-absolute and escape the preview
  onto the mirrored legacy site — subdomain previews are
  [#4](https://github.com/seandavi/bioconductor-website/issues/4).)
- **Every push to `main`** publishes an immutable `site/<sha>/` build and
  moves the `site/latest` pointer. Retention of old builds is
  [#2](https://github.com/seandavi/bioconductor-website/issues/2).
- **CI builds only the mutable surface** — prose pages, the live releases
  (currently 3.23 and 3.24), and `/next/`. The frozen releases (2.5–3.22) are
  archival: the Worker serves them from the mirrored legacy content in R2, and
  their routes never flip to Astro builds. The renderer discovers releases
  from whatever is in `astro/data/`, so this is a property of the data
  snapshot, not a code path.
- **Builds read a data snapshot**, not primary sources: CI pulls
  `_ci/site-data.tar.zst` (live releases' `astro/data/` plus the copied
  `astro/public/` assets). Refresh it by running the pipeline locally and
  re-uploading:

  ```sh
  just data
  tar -C astro -cf - data/site data/3.23 data/3.24 public | zstd -T0 -8 \
    | rclone rcat r2:bioc-site/_ci/site-data.tar.zst
  ```

  Scheduling that refresh is [#5](https://github.com/seandavi/bioconductor-website/issues/5).
  The full 35-release data — including the frozen 2.5–3.22 snapshot, which is
  **not regenerable from any live source** — lives at
  `_ci/site-data-full.tar.zst`; swap it in locally to rebuild an archival page
  deliberately.

## Quickstart

```sh
just install        # npm install in astro/
just data           # fetch data for the live releases into astro/data/
just build          # full static build -> astro/dist/
just dev            # dev server on :4321
```

`just --list` shows the finer-grained recipes (content only, one release's
packages.json, etc.). `astro/README.md` has renderer details and a
pipeline-free curl setup for the parity pages.

## Related repos

| repo | role |
|---|---|
| this one | renderer + pipeline; publishes builds |
| private infra repo | Cloudflare Worker, R2 storage, legacy-content sync, route table — decides what production serves |
| bioc-registry data plane | observes r-universe builds, evaluates the propagation gate, publishes the artifacts `/next/` renders |
| [Bioconductor/bioconductor.org](https://github.com/Bioconductor/bioconductor.org) | the legacy nanoc site; still the home of prose content until the markdown import lands here |

## Status

- Parity: package pages for 35 releases rebuild exactly (page count matches
  record count everywhere; 3.23 diffed path-by-path against the legacy build:
  7,614 identical paths, zero spurious). Prose coverage ~97%.
- `/next/`: check-results and package pages per universe, rendered from the
  data plane.
- Not here yet: the one-time markdown import of prose content (after which
  content changes happen in this repo by PR), search, and the cutover itself —
  the legacy site remains the production origin until the strangler migration
  flips routes to these builds.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). This project follows the
[Bioconductor Code of Conduct](CODE_OF_CONDUCT.md).

---

This repo was extracted (fresh history, 2026-08) from the private
bioconductor.org-migration repo; serving infrastructure, sync tooling, and
migration runbooks remain there.
