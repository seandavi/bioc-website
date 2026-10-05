// Sitemap index (#36). Replaces the legacy nanoc `<%= xml_sitemap %>` stub the
// Worker otherwise falls through to the mirror for.
import { shards, sitemapIndex } from '../lib/sitemap.js';

export const GET = () =>
  new Response(sitemapIndex(Object.keys(shards())), { headers: { 'Content-Type': 'application/xml' } });
