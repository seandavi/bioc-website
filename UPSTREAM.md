# Divergences from Bioconductor/bioconductor.org

The prose pages are built from [Bioconductor/bioconductor.org](https://github.com/Bioconductor/bioconductor.org),
the legacy nanoc site, which the core team still edits. Wherever this repository renders that
content differently from nanoc, or works around something in it, the difference is recorded here,
with the change that would make it unnecessary upstream. That's the list to work through when the
content moves into this repository, or to send upstream as pull requests before then.

**Rule:** any change to `pipeline/content.py` (or an Astro page that replaces an upstream page)
adds or updates an entry here in the same pull request. Issues about these carry the
`upstream-backport` label.

Status: **open**: only worked around here. **sent**: an upstream pull request exists. **done**:
fixed upstream, and the workaround here can go.

## Rendering workarounds

These exist because the upstream source relies on nanoc behavior.

| # | Upstream source | What goes wrong here | Workaround here | Upstream fix | Status |
|---|---|---|---|---|---|
| 1 | `layouts/components/homepage/join.html`, `layouts/components/quickstats.html`, included from `content/about/index.md` | Blank lines inside the partials. kramdown reads an HTML block through to its closing tag; CommonMark (`marked`) ends it at a blank line, and the rest renders as code ([#47](https://github.com/seandavi/bioc-infrastructure/issues/47)). | `compact_html()` in `pipeline/content.py` drops blank lines from every expanded partial, except inside `<pre>`/`<textarea>`. | Remove the blank lines from those two partials; nanoc's output is unchanged. | open |

## Translations of nanoc features

The pipeline stands in for these nanoc features. When the content moves here, each becomes an
Astro component or data file, and the upstream construct goes away.

| # | nanoc construct | Where upstream | How it's handled here | Astro-native replacement |
|---|---|---|---|---|
| 2 | `<%= config[:key] %>` (optionally `.sub(...)`) | `config.yaml`, many pages | Expanded by `resolve_erb()` | Values imported from a data file |
| 3 | `<%= render('/partial/') %>` | `layouts/**` | Expanded inline by `resolve_erb()`, then #1 | One Astro component per partial |
| 4 | `<%= ami_url(...) %>` | `lib/helpers.rb`; course materials, cloud AMI page | Link built by `sub_ami()` | Link written out, or a small component |
| 5 | `render('/_top_events/')` | homepage | Replaced with a slot filled from event data (`ERB_SLOTS`) | Events component |
| 6 | Pages generated from package data | `content/help/bioc-views/` | Skipped (`GENERATED`); built by the Astro side | Already native |
| 7 | Other ERB (helper calls, loops) | e.g. `developers/gitlog.md`, `help/publications.md` | Page flagged `erbUnresolved` and not rendered from the import | Port the page |
