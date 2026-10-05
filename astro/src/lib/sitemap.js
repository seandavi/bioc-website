import { loadPages } from './content.js';
import { liveVersions, reposFor, loadRepo, asArray } from './packages.js';

const ORIGIN = 'https://bioconductor.org';
// sitemaps.org limit per file. 50,000 short URLs is ~5 MB, far under the 50 MB cap.
const MAX_URLS = 50000;

// Canonical URLs only: the /release/ and /devel/ aliases (never the numbered
// versions, which carry canonicals pointing here), and nothing robots.txt
// disallows. Grouped so each group shards independently.
function groups() {
  const { release, devel } = liveVersions();
  const g = {
    // The renderable prose set of [...page].astro, minus the search page it
    // skips and robots.txt disallows.
    pages: loadPages()
      .filter((p) => p.renderable && p.url !== '/help/search/')
      .map((p) => p.url),
    release: [],
    devel: [],
  };
  for (const [channel, version] of [['release', release], ['devel', devel]]) {
    const base = `/packages/${channel}`;
    g[channel].push(`${base}/BiocViews.html`);
    for (const repo of reposFor(version)) {
      g[channel].push(`${base}/${repo}/`);
      for (const [name, pkg] of Object.entries(loadRepo(version, repo))) {
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
