// Build check for #36: run after `npm run build`. The sitemap index and its
// shards are well formed, list canonical URLs only, stay under the 50,000-URL
// limit, cover every rendered release package page, and list devel package pages
// only for packages with no release page (no devel index pages, no junk pages).
import { readdirSync, readFileSync, statSync } from 'node:fs';

const locs = (xml) => [...xml.matchAll(/<loc>([^<]*)<\/loc>/g)].map((m) => m[1]);
const fail = (msg) => { console.error(msg); process.exit(1); };

const read = (f) => {
  const xml = readFileSync(f, 'utf8');
  if (xml.includes('<%')) fail(`${f}: contains <%`);
  return xml;
};
const index = read('dist/sitemap.xml');
if (!index.includes('<sitemapindex')) fail('dist/sitemap.xml is not a sitemap index');

const urls = [];
for (const loc of locs(index)) {
  const f = 'dist/' + loc.replace('https://bioconductor.org/', '');
  const xml = read(f);
  const shard = locs(xml);
  if (shard.length === 0 || shard.length > 50000) fail(`${f}: ${shard.length} URLs`);
  if (statSync(f).size > 50 * 1024 * 1024) fail(`${f}: over 50 MB`);
  urls.push(...shard);
}

const bad = urls.filter((u) => !u.startsWith('https://bioconductor.org/') || /\/packages\/\d+\.\d+\//.test(u) || u.includes('/next/') || u.includes('//', 8));
if (bad.length) fail(`non-canonical URLs, e.g. ${bad.slice(0, 5).join(' ')}`);
const junk = urls.filter((u) => /^https:\/\/bioconductor\.org\/(help\/40[34]|examples|news\/template)\//.test(u));
if (junk.length) fail(`utility pages listed: ${junk.join(' ')}`);
const devel = urls.filter((u) => u.includes('/packages/devel/'));
const develIndex = devel.filter((u) => !/\/html\/[^/]+\.html$/.test(u));
if (develIndex.length) fail(`devel non-package pages listed, e.g. ${develIndex.slice(0, 5).join(' ')}`);
const releaseSet = new Set(urls.filter((u) => u.includes('/packages/release/')));
const develDup = devel.filter((u) => releaseSet.has(u.replace('/packages/devel/', '/packages/release/')));
if (develDup.length) fail(`devel pages that also have a release page, e.g. ${develDup.slice(0, 5).join(' ')}`);
if (new Set(urls).size !== urls.length) fail('duplicate URLs');

const release = readdirSync('dist/packages').filter((n) => /^\d+\.\d+$/.test(n)).sort((a, b) => a.localeCompare(b, undefined, { numeric: true })).at(-2);
const rendered = readdirSync(`dist/packages/${release}`, { recursive: true }).filter((f) => /\/html\/[^/]+\.html$/.test(f)).length;
const listed = urls.filter((u) => /\/packages\/release\/.*\/html\/[^/]+\.html$/.test(u)).length;
if (listed < rendered) fail(`sitemap lists ${listed} release package pages, build rendered ${rendered}`);
console.log(`sitemap ok: ${urls.length} URLs, ${listed} release package pages (rendered: ${rendered}), ${devel.length} devel-only package pages`);
