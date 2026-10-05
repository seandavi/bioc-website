// Build check for #33: run after `npm run build`. dist/robots.txt allows the
// package pages and vignettes crawlers need and blocks the rest. Disallow-only
// file, so a path is blocked when any rule matches (Google syntax: `*`, `$`).
import { readFileSync } from 'node:fs';

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
  '/biocViews/',
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
];
const bad = [...allowed.filter(blocked).map((p) => `${p}: blocked`), ...denied.filter((p) => !blocked(p)).map((p) => `${p}: allowed`)];
if (!txt.includes('\nSitemap: https://bioconductor.org/sitemap.xml\n')) bad.push('no Sitemap line');
if (bad.length) { console.error(bad.join('\n')); process.exit(1); }
console.log(`robots ok: ${rules.length} Disallow rules`);
