import { loadPages } from './content.js';
import { liveVersions, reposFor, loadRepo, asArray } from './packages.js';

const ORIGIN = 'https://bioconductor.org';
// sitemaps.org limit per file. 50,000 short URLs is ~5 MB, far under the 50 MB cap.
const MAX_URLS = 50000;

// bioc-edge's redirects.json is the source of truth for these: the build still
// renders them, but production answers 301, and a sitemap must not list a
// redirect. Everything under how-to/ moved to contributions.bioconductor.org
// except the two index pages (checked with curl, 2026-10-05).
const redirected = (url) =>
  (url.startsWith('/developers/how-to/') && url !== '/developers/how-to/' && url !== '/developers/how-to/git/') ||
  url === '/developers/package-end-of-life/' ||
  url === '/developers/package-submission/';

// Not content: error pages, the nanoc example/template files (checked
// 2026-10-05: 'Example Index File', 'Access Forbidden', 'Page Not Found', and
// the 3.18 release-announcement template).
const junk = new Set(['/help/403/', '/help/404/', '/examples/', '/examples/markdown/', '/news/template/']);

// Canonical URLs only: the /release/ and /devel/ aliases (never the numbered
// versions, which carry canonicals pointing here), and nothing robots.txt
// disallows. Devel pages are near-duplicates of release pages and equally
// self-canonical, so devel lists only packages with no release page, and no
// devel index pages. Grouped so each group shards independently.
function groups() {
  const { release, devel } = liveVersions();
  const g = {
    // The renderable prose set of [...page].astro, minus the search page it
    // skips and robots.txt disallows, and minus URLs the Worker redirects.
    pages: loadPages()
      .filter((p) => p.renderable && p.url !== '/help/search/' && !redirected(p.url) && !junk.has(p.url))
      .map((p) => p.url),
    release: [],
    devel: [],
  };
  const releaseRepos = Object.fromEntries(reposFor(release).map((repo) => [repo, loadRepo(release, repo)]));
  for (const [channel, version] of [['release', release], ['devel', devel]]) {
    const base = `/packages/${channel}`;
    if (channel === 'release') g[channel].push(`${base}/BiocViews.html`);
    for (const repo of reposFor(version)) {
      if (channel === 'release') g[channel].push(`${base}/${repo}/`);
      for (const [name, pkg] of Object.entries(loadRepo(version, repo))) {
        if (channel === 'devel' && releaseRepos[repo]?.[name]) continue;
        g[channel].push(`${base}/${repo}/html/${name}.html`);
        // Release vignettes answer the "how do I ..." queries; the data has
        // no dates, so no <lastmod>.
        if (channel === 'release') {
          for (const v of asArray(pkg.vignettes)) {
            if (v.endsWith('.html')) g[channel].push(`${base}/${repo}/vignettes/${name}/inst/doc/${v.split('/').pop()}`);
          }
        }
      }
    }
  }
  return g;
}

// shard name ('release-1') -> URL paths
export function shards() {
  const out = {};
  for (const [group, urls] of Object.entries(groups())) {
    for (let i = 0; i * MAX_URLS < urls.length; i++) {
      out[`${group}-${i + 1}`] = urls.slice(i * MAX_URLS, (i + 1) * MAX_URLS);
    }
  }
  return out;
}

const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const xml = (root, items) =>
  `<?xml version="1.0" encoding="UTF-8"?>\n<${root} xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${items}</${root}>\n`;

export const urlset = (paths) => xml('urlset', paths.map((p) => `<url><loc>${esc(ORIGIN + p)}</loc></url>\n`).join(''));
export const sitemapIndex = (names) =>
  xml('sitemapindex', names.map((n) => `<sitemap><loc>${ORIGIN}/sitemap-${n}.xml</loc></sitemap>\n`).join(''));
