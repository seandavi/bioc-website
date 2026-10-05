// Absolute apex URL for <link rel="canonical">. Repeated slashes collapse (the
// edge serves /packages//release/... too) and a trailing index.html drops, so
// 'about/index.html' canonicalises to the '/about/' URL the site links to.
// pages/next/index.astro builds to next.html (format 'file') but is linked as /next/.
export function canonicalUrl(pathname) {
  const path = pathname.replace(/\/{2,}/g, '/').replace(/\/index\.html$/, '/').replace(/^\/next\.html$/, '/next/');
  return 'https://bioconductor.org' + path;
}
