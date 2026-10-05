// Absolute apex URL for <link rel="canonical">. Repeated slashes collapse (the
// edge serves /packages//release/... too) and a trailing index.html drops, so
// 'about/index.html' canonicalises to the '/about/' URL the site links to.
export function canonicalUrl(pathname) {
  return 'https://bioconductor.org' + pathname.replace(/\/{2,}/g, '/').replace(/\/index\.html$/, '/');
}
