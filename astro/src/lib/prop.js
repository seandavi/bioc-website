// Data provider for the bioc-prop data plane (the propagation gate).
// Landing pages and check pages render from what *propagated*, not whatever
// r-universe last built: the prop index is the authority on versions, the
// observation archive on check status.
//
// Metadata (Title, Description, authors, vignettes) comes from the index
// entries' `meta`/`desc` -- archived by the observer, so it describes the
// propagated version and the build has no hard dependency on r-universe.
// Only the volatile trust signals (downloads, stars, usedby) and the
// live-version skew banner still ask r-universe, best-effort: those change
// too often to archive and losing them must never fail a build.

const BASE =
  process.env.PROP_DATA_BASE ?? 'https://bioc-prop.seandavi.workers.dev/data';

// release first: it is the one people land on.
export const UNIVERSES = ['bioc-release', 'bioc'];

const memo = new Map();
function getJSON(url) {
  if (!memo.has(url)) {
    memo.set(
      url,
      fetch(url).then((r) => {
        if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
        return r.json();
      }),
    );
  }
  return memo.get(url);
}

// package -> {version, sha256, ts, bioccheck, artifacts: [{os, r, sha256, file}]}
export function propIndex(universe) {
  return getJSON(`${BASE}/prop/${universe}/index.json`);
}

export async function latestObservation(universe) {
  const state = await getJSON(`${BASE}/state/${universe}/latest`);
  return getJSON(`${BASE}/${state.key}`);
}

export function casUrl(universe, artifact) {
  return `${BASE}/prop/${universe}/cas/${artifact.sha256}`;
}

// Volatile-only: monthly downloads, dependents, stars, and the version the
// live build is at (for the skew banner). Best-effort by design -- an
// r-universe outage degrades pages to "no trust signals", never a failed build.
export async function liveSignals(universe) {
  try {
    const list = await getJSON(
      `https://${universe}.r-universe.dev/api/packages?limit=100000&fields=Version,_downloads,_usedby,_stars`,
    );
    return new Map(list.map((m) => [m.Package, m]));
  } catch {
    return new Map();
  }
}

// DCF dependency string -> the contract's array shape ("pkg (>= 1.0)" items).
const depList = (s) => (s ? s.split(',').map((x) => x.trim()).filter(Boolean) : undefined);

// Map a prop-index entry (+ optional live signals) into the packages.json
// contract PackageDetail already renders. Everything stable is the archived
// propagated version's own metadata; `live` only feeds the skew banner and
// trust signals.
export function toContractRecord(entry, live) {
  const m = entry.meta ?? {};
  const d = entry.desc ?? {};
  return {
    Version: entry.version,
    // Non-null when the live build has moved past what propagated: the page
    // shows gate truth, this records the skew for the preview banner.
    buildVersion: live?.Version && live.Version !== entry.version ? live.Version : null,
    Title: m.Title,
    Description: m.Description,
    Author: m.Author,
    Maintainer: m.Maintainer,
    License: d.License,
    URL: m.URL,
    BugReports: m.BugReports,
    SystemRequirements: m.SystemRequirements,
    biocViews: m.biocViews ? m.biocViews.split(',').map((x) => x.trim()) : [],
    vignettes: (m.vignettes ?? []).map((v) => v.filename).filter(Boolean),
    vignetteTitles: (m.vignettes ?? []).map((v) => v.title).filter(Boolean),
    Depends: depList(d.Depends),
    Imports: depList(d.Imports),
    LinkingTo: depList(d.LinkingTo),
    Suggests: depList(d.Suggests),
    Enhances: depList(d.Enhances),
    // Trust signals, straight from r-universe. downloads.count is monthly.
    downloads: live?._downloads?.count,
    usedby: live?._usedby,
    stars: live?._stars,
    // Unix seconds of the last upstream commit; rendered as a date, never
    // relative time (build output must not depend on when it was built).
    updated: m.commit?.time,
  };
}

// Worst-first ordering for the check matrix.
const SEVERITY = { ERROR: 0, FAIL: 0, FAILURE: 0, WARNING: 1, NOTE: 2, OK: 3 };
export function severity(check) {
  return SEVERITY[String(check ?? '').toUpperCase()] ?? 3;
}
