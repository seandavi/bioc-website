// robots.txt (#33). astro/public/ is copied from upstream, so the build emits
// it here; otherwise the Worker falls through to the legacy mirror's copy,
// which blocks /packages/release/, /packages/devel/ and /biocViews/.
import { versions } from '../lib/packages.js';

// Release numbers older than the package data (JSON starts at 2.5), plus every
// numbered release the build knows. The live release and devel are listed too:
// they are served at /packages/release|devel/ and their numbered URLs only
// duplicate those (canonicals: #34).
const before2_5 = ['1.8', '1.9', '2.0', '2.1', '2.2', '2.3', '2.4'];

const disallow = [
  '/checkResults/', '/packages/submitted/', '/packages/misc/', '/packages/lindsey/',
  '/packages/omegahat/', '/repository/', '/installScripts/', '/data/', '/datafiles/',
  '/stats/', '/dataann-stats/', '/dataexp-stats/',
  // Every search URL is unique and has no content of its own.
  '/help/search/',
  // Package tarballs and binaries, wherever they are mirrored.
  '/*/src/contrib/', '/*/bin/', '/*.tar.gz$', '/*.tgz$', '/*.zip$',
  // Double slashes: the same page under a different URL.
  '/*//',
  // Legacy aliases of the release/devel trees.
  '/packages/bioc/', '/packages/data/',
  // kept until seandavi/bioc-website#50 (canonical/noindex on these URLs, bioc-edge#55)
  ...[...before2_5, ...versions()].map((v) => `/packages/${v}/`),
];

export const GET = () =>
  new Response(
    `User-agent: *\n${disallow.map((p) => `Disallow: ${p}\n`).join('')}\nSitemap: https://bioconductor.org/sitemap.xml\n`,
    { headers: { 'Content-Type': 'text/plain' } },
  );
