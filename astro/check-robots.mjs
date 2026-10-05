// Build check for #33: run after `npm run build`. dist/robots.txt allows the
// package pages and vignettes crawlers need and blocks the rest. Disallow-only
// file, so a path is blocked when any rule matches (Google syntax: `*`, `$`).
// Also fails if the legacy upstream robots.txt (which blocks /packages/release/)
// ended up in dist/ instead of the generated one, and if any URL in a built
// sitemap-*.xml is blocked.
import { readdirSync, readFileSync } from 'node:fs';

const txt = readFileSync('dist/robots.txt', 'utf8');
const rules = [...txt.matchAll(/^Disallow: (\S+)$/gm)].map(([, p]) =>
  new RegExp('^' + p.replace(/[.+?^{}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*')),
);
const blocked = (path) => rules.some((r) => r.test(path));

const allowed = [
  '/packages/release/bioc/html/DESeq2.html',
  '/packages/devel/bioc/html/DESeq2.html',
  '/packages/release/data/experiment/html/airway.html',
  '/packages/release/bioc/vignettes/DESeq2/inst/doc/DESeq2.html',
  '/style/base/colors.css',
  '/js/jquery.js',
  '/images/logo/svg/Logo.svg',
  '/favicon.ico',
  '/_astro/x.js',
  '/pagefind/pagefind.js',
  '/sitemap.xml',
  '/sitemap-release-1.xml',
];
const denied = [
  '/checkResults/',
  '/help/search/?search-bar=x',
  '/packages/1.8/bioc/html/DESeq2.html',
  '/packages/3.23/bioc/html/DESeq2.html',
  '/packages/3.24/bioc/html/DESeq2.html',
  '/packages/release/bioc/src/contrib/DESeq2_1.52.0.tar.gz',
  '/packages/release/bioc/bin/windows/contrib/4.6/DESeq2_1.52.0.zip',
  '//packages//release/',
  '//packages/release/',
  '//x',
  '/next/',
  '/next/bioc/package/DESeq2.html',
];
const bad = [...allowed.filter(blocked).map((p) => `${p}: blocked`), ...denied.filter((p) => !blocked(p)).map((p) => `${p}: allowed`)];
if (!txt.includes('\nSitemap: https://bioconductor.org/sitemap.xml\n')) bad.push('no Sitemap line');
if (txt.includes('Disallow: /packages/release/')) bad.push('legacy robots.txt: blocks /packages/release/');

// Every URL we tell crawlers about must be crawlable.
const sitemaps = readdirSync('dist').filter((f) => /^sitemap-.*\.xml$/.test(f));
let listed = 0;
for (const f of sitemaps) {
  for (const [, loc] of readFileSync(`dist/${f}`, 'utf8').matchAll(/<loc>([^<]*)<\/loc>/g)) {
    listed++;
    const path = loc.replace(/&amp;/g, '&').replace(/^https:\/\/bioconductor\.org/, '');
    if (blocked(path)) bad.push(`${f}: lists ${path}, which robots.txt blocks`);
  }
}
if (bad.length) { console.error(bad.join('\n')); process.exit(1); }
console.log(`robots ok: ${rules.length} Disallow rules, ${listed} sitemap URLs from ${sitemaps.length} files checked`);
