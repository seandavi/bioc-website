"""Prose content from the site's own source repository.

`Bioconductor/bioconductor.org` is a genuine primary source: it is where the
hand-written pages actually live, and it has nothing to do with the hosts being
retired. Roughly 536 body files -- about, help, developers, news, and the
course-materials archive -- plus 172 metadata-only event records.

What this module does is *normalisation*, and that is the whole point of it
being on the pipeline side of the seam. nanoc keeps front matter out-of-band, in
a sibling `.yaml` beside each body file, which is a nanoc convention no other
renderer shares. Rather than teach Astro that convention, the pipeline reads
both halves and emits one flat `pages.json` that any renderer can consume.

ERB is the one genuine incompatibility, and it is much smaller than it looks:
of 536 body files, 504 contain no ERB at all and only 11 have more than two
tags. Those are recorded in the output (`erb: true`) and reported, rather than
being silently emitted half-rendered.
"""

import json
import os
import re
import sys

import yaml

# A real ERB tag: <% ... %> or <%= ... %>, on one line.
#
# Requiring the closing %> on the same line matters. Counting bare `<%` flags
# R's `%<%` operator, which appears in package NEWS text -- it put a 6,973-line
# release-notes page containing no ERB whatsoever into the "cannot render"
# bucket. Every ERB tag in this content tree is single-line, so this is exact
# rather than a heuristic.
ERB = re.compile(r"<%[-=]?[^\n%]*%>")

# The two constructs that make up nearly all of the ERB actually used:
# a config lookup (optionally chained with .sub) and a static partial include.
ERB_CONFIG = re.compile(
    r"<%=\s*config\[:(\w+)\](?:\[:(\w+)\])?\s*(?:\.sub\(\s*[\"'](.*?)[\"']\s*,"
    r"\s*[\"'](.*?)[\"']\s*\))?\s*%>")
ERB_RENDER = re.compile(r"<%=\s*render\(\s*['\"]([^'\"]+)['\"]\s*\)\s*%>")

# `ami_url` is a one-line link builder in lib/helpers.rb. Worth special-casing
# because it is the only thing standing between us and eight course-material
# pages plus the cloud-AMI page.
ERB_AMI = re.compile(
    r"<%=\s*ami_url[\s(]+(?:['\"](?P<literal>[\w-]+)['\"]"
    r"|config\[:ami_ids\]\[:(?P<key>\w+)\])\s*\)?\s*%>")

# Partials that loop over build data rather than emitting static markup. These
# cannot be expanded here -- the data belongs to the renderer -- so they become
# named slots that the Astro side fills from the same JSON the pipeline writes.
# Keeping them as explicit slots (rather than dropping them) means a page that
# needs one cannot silently render without it.
ERB_SLOTS = [
    (re.compile(r"<%=\s*render\(\s*['\"]/_top_events/['\"].*?%>"), "events"),
]

# nanoc's `filesystem_unified` treats these as page bodies; everything else in
# content/ is an asset or a stray artifact.
BODY_EXT = (".md", ".html", ".haml")

# Pages whose body is generated at build time from package data rather than
# written by hand. They are placeholders in the repo, so copying them verbatim
# would produce a page that renders the template instead of the content.
GENERATED = re.compile(r"^/help/bioc-views/")


def url_for(rel):
    """Content path -> published URL, following nanoc's routing.

    `filesystem_unified` turns `content/help/faq.md` into identifier `/help/faq/`
    and the catch-all route appends `index.html`. So the URL is the path with the
    extension dropped and a trailing slash, except that an `index` basename
    collapses into its parent directory.
    """
    rel = rel.replace(os.sep, "/")
    stem = rel.rsplit(".", 1)[0]
    parts = stem.split("/")
    if parts[-1] == "index":
        parts = parts[:-1]
    return "/" + "/".join(parts) + "/" if parts else "/"


def read_meta(path):
    """The sidecar `.yaml` beside a body file. Missing is normal (12 of 536)."""
    side = path.rsplit(".", 1)[0] + ".yaml"
    if not os.path.exists(side):
        return {}
    try:
        with open(side, encoding="utf-8", errors="replace") as fh:
            doc = yaml.safe_load(fh.read())
        return doc if isinstance(doc, dict) else {}
    except Exception as e:
        print("  ! bad sidecar %s: %s" % (side, e), file=sys.stderr)
        return {}


def load_config(repo):
    """config.yaml — release/devel versions, R versions, mirrors, AMI ids.

    nanoc uses this as its site config; for us it is just another primary
    source, and it is what most of the surviving ERB actually reads."""
    path = os.path.join(repo, "config.yaml")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        return yaml.safe_load(fh) or {}


def load_partial(repo, ref):
    """Resolve a nanoc render() target to the partial's source.

    `/components/homepage/learn/` -> layouts/components/homepage/learn.html,
    `/_top_events/` -> layouts/_top_events.html.
    """
    rel = ref.strip("/")
    for candidate in (rel + ".html", rel + ".haml"):
        path = os.path.join(repo, "layouts", candidate)
        if os.path.exists(path):
            with open(path, encoding="utf-8", errors="replace") as fh:
                return fh.read()
    return None


# Blocks where blank lines are content, not layout.
VERBATIM = re.compile(r"(<(pre|textarea)\b.*?</\2>)", re.S | re.I)


def compact_html(html):
    """Drop blank lines from an expanded partial, except inside <pre>/<textarea>.

    nanoc renders Markdown with kramdown, which reads an HTML block through to
    its closing tag. marked follows CommonMark, where a blank line ends an HTML
    block: the rest of the partial is then parsed as Markdown, and its lines
    indented 4+ spaces become code blocks (issue #47, /about/). Blank lines
    between tags are insignificant in HTML, so removing them keeps the partial
    one HTML block under either parser. Recorded in UPSTREAM.md for backport.
    """
    parts = VERBATIM.split(html)
    # split() with two groups yields [text, block, tagname, text, block, tagname, ...]
    out = []
    for i in range(0, len(parts), 3):
        out.append(re.sub(r"\n[ \t]*(?=\n)", "", parts[i]))
        if i + 1 < len(parts):
            out.append(parts[i + 1])
    return "".join(out)


def resolve_erb(body, repo, cfg, depth=0):
    """Expand the ERB we can evaluate; leave the rest alone.

    Handles exactly two constructs, because between them they account for
    nearly all the ERB in this content tree:

      <%= config[:key] %>          a site-config lookup, optionally .sub()'d
      <%= render('/partial/') %>   a static partial include, expanded inline

    Anything else -- helper calls, loops, build-data lookups -- is left in
    place, so `ERB.search()` afterwards still reports the page as unrenderable.
    Partial expansion recurses, since partials include partials.
    """
    if depth > 6:                      # cycle guard; nesting here is 2-3 deep
        return body

    def sub_config(m):
        key, sub_key, find, repl = m.group(1), m.group(2), m.group(3), m.group(4)
        val = cfg.get(key)
        if isinstance(val, dict) and sub_key:
            val = val.get(sub_key)
        if val is None:
            return m.group(0)          # unknown key: leave it, stay detectable
        val = str(val)
        return val.replace(find, repl, 1) if find is not None else val

    def sub_render(m):
        part = load_partial(repo, m.group(1))
        if part is None:
            return m.group(0)
        return compact_html(resolve_erb(part, repo, cfg, depth + 1))

    def sub_ami(m):
        ami = m.group("literal") or (cfg.get("ami_ids") or {}).get(m.group("key") or "")
        if not ami:
            return m.group(0)
        return ("<a href='https://console.aws.amazon.com/ec2/home"
                "?region=us-east-1#launchAmi=%s'>%s</a>" % (ami, ami))

    for rx, name in ERB_SLOTS:
        body = rx.sub("<!--slot:%s-->" % name, body)
    body = ERB_AMI.sub(sub_ami, body)
    body = ERB_CONFIG.sub(sub_config, body)
    body = ERB_RENDER.sub(sub_render, body)
    return body


def collect(repo, subdir="content"):
    """Walk the content tree. Returns (pages, events, report)."""
    root = os.path.join(repo, subdir)
    if not os.path.isdir(root):
        raise SystemExit("no content tree at %s -- run `just fetch-site` first" % root)

    cfg = load_config(repo)
    pages, events, erb_heavy, skipped = [], [], [], []
    for dirpath, _, filenames in os.walk(root):
        for fn in sorted(filenames):
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, root)
            stem, ext = os.path.splitext(fn)

            if ext == ".yaml":
                # Metadata-only items -- the 171 events -- have no body file.
                if any(os.path.exists(os.path.join(dirpath, stem + e)) for e in BODY_EXT):
                    continue
                meta = read_meta(path) or {}
                if meta.get("start") or meta.get("event_host"):
                    meta["url"] = url_for(rel)
                    events.append(meta)
                continue

            if ext not in BODY_EXT:
                continue

            url = url_for(rel)
            if GENERATED.match(url):
                skipped.append(url)
                continue

            with open(path, encoding="utf-8", errors="replace") as fh:
                body = fh.read()

            # Expand the ERB we can evaluate, then judge what is left. Judging
            # before expanding is what made the homepage look unrenderable: it
            # is 8 lines of nothing but static partial includes.
            body = resolve_erb(body, repo, cfg)
            leftover = ERB.findall(body)
            if leftover:
                erb_heavy.append(url)

            meta = read_meta(path)
            # `hero:` names a partial in the sidecar rather than the body, so it
            # is resolved the same way and carried alongside. The layout decides
            # where it goes; the pipeline only supplies the markup.
            hero = None
            if meta.get("hero"):
                raw = load_partial(repo, meta["hero"])
                if raw is not None:
                    hero = resolve_erb(raw, repo, cfg)

            pages.append({
                "url": url,
                "hero": hero,
                "fullwidth": bool(meta.get("fullwidth")),
                "source": rel,
                # .haml is Ruby-specific templating; there are only a couple and
                # they are flagged rather than mangled into HTML.
                "format": {"md": "md", "html": "html", "haml": "haml"}[ext.lstrip(".")],
                "title": meta.get("title") or stem.replace("-", " ").title(),
                "meta": {k: v for k, v in meta.items() if k != "title"},
                # What could not be evaluated, so the renderer can skip the page
                # rather than ship visible <% %>. Empty means fully resolved.
                "erbUnresolved": sorted(set(leftover))[:5],
                "body": body,
            })

    pages.sort(key=lambda p: p["url"])
    events.sort(key=lambda e: str(e.get("start") or ""), reverse=True)
    report = {
        "pages": len(pages),
        "events": len(events),
        "with_erb": sum(1 for p in pages if p["erbUnresolved"]),
        "erb_heavy": sorted(erb_heavy),
        "haml": sorted(p["url"] for p in pages if p["format"] == "haml"),
        "skipped_generated": len(skipped),
    }
    return pages, events, report


def write(repo, outdir):
    pages, events, report = collect(repo)
    dest = os.path.join(outdir, "site")
    os.makedirs(dest, exist_ok=True)
    for name, obj in (("pages.json", pages), ("events.json", events)):
        with open(os.path.join(dest, name), "w", encoding="utf-8") as fh:
            # YAML parses unquoted dates into date objects; the event sidecars are
            # full of them. ISO strings are what the renderer wants anyway.
            json.dump(obj, fh, indent=1, default=str)
    # The site-wide announcement banner is a hand-edited fragment in the
    # upstream layouts, not content: carry it verbatim so an upstream edit
    # flows through `just data` with no renderer change. Absent or fully
    # commented-out upstream -> empty file -> no banner.
    ann = os.path.join(repo, "layouts", "components", "announcement.html")
    with open(os.path.join(dest, "announcement.html"), "w", encoding="utf-8") as fh:
        fh.write(open(ann, encoding="utf-8").read() if os.path.exists(ann) else "")
    print("[content] %d pages, %d events -> %s" % (len(pages), len(events), dest),
          file=sys.stderr)
    print("[content] %d contain ERB (%d heavily), %d haml, %d generated pages skipped"
          % (report["with_erb"], len(report["erb_heavy"]), len(report["haml"]),
             report["skipped_generated"]), file=sys.stderr)
    return report
