import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';

// Same resolution rule as lib/packages.js: from the project root, not
// import.meta.url, because Vite rewrites module URLs during the build.
const DATA = join(process.cwd(), 'data', 'site');

function read(name) {
  const f = join(DATA, name);
  // Fail loudly: a missing data file must not silently yield zero pages. This
  // build has already been burned once by a renderer that "succeeded" with no
  // output because its input was absent.
  if (!existsSync(f)) {
    throw new Error(`missing site data: ${f} -- run \`just data-content\` first`);
  }
  return JSON.parse(readFileSync(f, 'utf8'));
}

// Which pages are renderable is decided by the pipeline, not repeated here.
// `erbUnresolved` lists the ERB tags it could not evaluate; empty means the
// page is fully resolved. A hardcoded list used to live here and drifted the
// moment the pipeline got better at resolving ERB.
export function loadPages() {
  return read('pages.json').map((p) => ({
    ...p,
    renderable: !(p.erbUnresolved && p.erbUnresolved.length),
  }));
}

export function loadEvents() {
  return read('events.json');
}

/** Upcoming events first, then most recent past ones — what `_top_events` did. */
export function topEvents(events, limit = 5) {
  const today = new Date().toISOString().slice(0, 10);
  const key = (e) => String(e.start ?? '');
  const upcoming = events.filter((e) => key(e) >= today).sort((a, b) => key(a).localeCompare(key(b)));
  const past = events.filter((e) => key(e) < today).sort((a, b) => key(b).localeCompare(key(a)));
  return [...upcoming, ...past].slice(0, limit);
}

/**
 * Live-site date shapes, exactly: "02 December 2025", "19 - 20 November 2026"
 * (range within one month), "28 June - 02 July 2026" (one year). Days are
 * always zero-padded and the separator is a spaced hyphen, not an en dash.
 */
export function eventDate(e) {
  if (!e.start) return '';
  const d = (s) => new Date(s + 'T00:00:00Z');
  const pad = (n) => String(n).padStart(2, '0');
  const part = (x, opts) => x.toLocaleDateString('en-GB', { ...opts, timeZone: 'UTC' });
  const full = (x) => `${pad(x.getUTCDate())} ${part(x, { month: 'long', year: 'numeric' })}`;
  const s = d(e.start);
  if (!e.end || e.end === e.start) return full(s);
  const t = d(e.end);
  if (s.getUTCFullYear() === t.getUTCFullYear() && s.getUTCMonth() === t.getUTCMonth())
    return `${pad(s.getUTCDate())} - ${pad(t.getUTCDate())} ${part(s, { month: 'long', year: 'numeric' })}`;
  if (s.getUTCFullYear() === t.getUTCFullYear())
    return `${pad(s.getUTCDate())} ${part(s, { month: 'long' })} - ${full(t)}`;
  return `${full(s)} - ${full(t)}`;
}
