import { defineConfig } from 'astro/config';

export default defineConfig({
  // 'file' emits <slug>.html rather than <slug>/index.html, so the generated
  // paths match the existing site exactly: /packages/3.23/bioc/html/limma.html
  build: { format: 'file' },
  // The legacy site is served from the domain root; keep URLs identical.
  site: 'https://bioconductor.org',
  // Bind to all interfaces so `npm run dev` is reachable over the tailnet.
  server: { host: true, port: 4321 },
  // Vite rejects any Host header that isn't localhost or a bare IP, which
  // makes the tailnet DNS name 403 while its IP works. Leading dot = suffix.
  // `server` and `preview` are separate Vite servers with separate config, so
  // setting only one leaves `astro preview` 403ing on the same hostname.
  vite: {
    server: { allowedHosts: ['.ts.net'] },
    preview: { allowedHosts: ['.ts.net'] },
  },
});
