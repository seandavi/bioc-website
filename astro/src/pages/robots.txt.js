// robots.txt (#33). The build emits it here (bioc.py does not copy upstream's
// into astro/public/); otherwise the Worker falls through to the legacy
// mirror's copy, which blocks /packages/release/ and /packages/devel/.
import { versions } from '../lib/packages.js';

// Every numbered release there has ever been, derived from the version numbers
// and NOT from the data on disk: CI builds from a snapshot holding only the two
// live releases, so listing "the releases the build knows" silently dropped
// 2.5-3.22 (they are legacy mirror pages with no canonical, and must stay
// blocked until seandavi/bioc-website#50). The live release and devel are listed
// too: they are served at /packages/release|devel/ and their numbered URLs only
// duplicate those (canonicals: #34).
const FIRST_MAJOR_LAST_MINOR = { 1: 9, 2: 14 }; // 1.8-1.9, 2.0-2.14: frozen
const newest = versions().at(-1);
const [newestMajor, newestMinor] = newest.split('.').map(Number);
if (newestMajor !== 3) {
  // 3.x is the current major; when 4.0 appears this needs 3's last minor.
  throw new Error(`robots.txt: newest release is ${newest}; add the last 3.x minor to FIRST_MAJOR_LAST_MINOR`);
}
const range = (n, from = 0) => Array.from({ length: n - from + 1 }, (_, i) => from + i);
const numbered = [
  ...range(FIRST_MAJOR_LAST_MINOR[1], 8).map((m) => `1.${m}`),
  ...range(FIRST_MAJOR_LAST_MINOR[2]).map((m) => `2.${m}`),
  ...range(newestMinor).map((m) => `3.${m}`),
];

const disallow = [
  '/checkResults/', '/packages/submitted/', '/packages/misc/', '/packages/lindsey/',
  '/packages/omegahat/', '/repository/', '/installScripts/', '/data/', '/datafiles/',
  '/stats/', '/dataann-stats/', '/dataexp-stats/',
  // Every search URL is unique and has no content of its own.
  '/help/search/',
  // Package tarballs and binaries, wherever they are mirrored.
  '/*/src/contrib/', '/*/bin/', '/*.tar.gz$', '/*.tgz$', '/*.zip$',
  // Double slashes: the same page under a different URL ('/*//' needs a
  // character before the pair, so a leading '//' is listed on its own).
  '//', '/*//',
  // The /next/ preview track is kept out of search (its pages are self-canonical).
  '/next/',
  // Legacy aliases of the release/devel trees.
  '/packages/bioc/', '/packages/data/',
  // kept until seandavi/bioc-website#50 (canonical/noindex on these URLs, bioc-edge#55)
  ...numbered.map((v) => `/packages/${v}/`),
];

export const GET = () =>
  new Response(
    `User-agent: *\n${disallow.map((p) => `Disallow: ${p}\n`).join('')}\nSitemap: https://bioconductor.org/sitemap.xml\n`,
    { headers: { 'Content-Type': 'text/plain' } },
  );
