# Contributing

Thanks for helping build the next-generation bioconductor.org. This repo holds
the site's renderer (`astro/`) and the data pipeline that feeds it
(`pipeline/`, driven by `./bioc.py`). Start with the [README](README.md) for
the architecture and quickstart.

## What contributions go where

- **Site rendering, layout, components, `/next/` pages** — here. PRs welcome.
- **Data pipeline** (how `astro/data/` gets built from primary sources) — here.
- **Prose content** (the text of www pages) — for now, still the
  [Bioconductor/bioconductor.org](https://github.com/Bioconductor/bioconductor.org)
  repo, which this pipeline reads. A one-time markdown import into this repo is
  planned; after that, content changes happen here by PR.
- **Package landing-page data** (titles, maintainers, check results) — not
  editable anywhere in a website repo; it comes from package sources via
  r-universe and the build system.

## Development

```sh
just install     # npm install in astro/
just data        # fetch data for the live releases into astro/data/
just build       # full static build -> astro/dist/
just dev         # dev server on :4321
```

`astro/README.md` documents a pipeline-free setup (curl the JSON contract from
the live site) if you only want to touch the renderer.

## Pull requests

- Every PR gets a **preview URL** posted as a comment once CI builds it — check
  your change there, that build is exactly what production would serve.
- Keep PRs focused; the build is fast, so small PRs iterate quickly.
- The `packages.json` contract is shared with the legacy renderer during the
  migration — changes to what the renderer *consumes* need a matching pipeline
  change and a note in the PR.

## Conduct

This project follows the
[Bioconductor Code of Conduct](CODE_OF_CONDUCT.md).
