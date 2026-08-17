# Advisory-group deck

The slide version of [`../OVERVIEW.md`](../OVERVIEW.md). Same argument, ~30
slides.

```sh
quarto add seandavi/quarto-livefigures   # once; needs Node >= 18
quarto render slides.qmd                 # -> slides.html, self-contained
```

Figures are **sources**, not exports: `figures/*.dot`, `.noml`, and `.vl.json`
are rendered at build time by
[livefigures](https://github.com/seandavi/quarto-livefigures). Edit the source
and re-render — there is no image to keep in sync, and nothing binary in git.

To check a figure on its own before rendering the whole deck:

```sh
node _extensions/seandavi/livefigures/cli.mjs render figures/before-after.dot -o /tmp/f.png
```

The rendered `slides.html` is gitignored. Build it when you need it.
