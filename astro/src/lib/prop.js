// Data provider for the bioc-prop data plane (the propagation gate).
// Landing pages and check pages render from what *propagated*, not whatever
// r-universe last built: the prop index is the authority on versions, the
// observation archive on check status.
//
// Metadata (Title, Description, authors, vignettes) is NOT in the observations
// -- the observer keeps build-relevant fields only. Until the data plane
// publishes a metadata artifact, it is fetched from r-universe directly at
// build time here, and the version is pinned to what the gate propagated.

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

// ponytail: dev-time stopgap -- becomes a data-plane artifact so builds never
// depend on r-universe being up (and so the metadata is the *propagated*
// version's, not the latest build's; see buildVersion below).
const META_FIELDS =
  'Version,Title,Description,Author,Maintainer,License,URL,BugReports,' +
  'SystemRequirements,biocViews,_vignettes,_dependencies,' +
  '_downloads,_usedby,_stars,_commit';
export async function metadata(universe) {
  const list = await getJSON(
    `https://${universe}.r-universe.dev/api/packages?limit=100000&fields=${META_FIELDS}`,
  );
  return new Map(list.map((m) => [m.Package, m]));
}

const ROLE_FIELD = {
  depends: 'Depends',
  imports: 'Imports',
  linkingto: 'LinkingTo',
  suggests: 'Suggests',
  enhances: 'Enhances',
};

// Map r-universe metadata + a prop-index entry into the packages.json contract
// PackageDetail already renders. Version comes from the gate, never the build.
export function toContractRecord(meta, entry) {
  const rec = {
    Version: entry.version,
    // Non-null when the live build has moved past what propagated: the page
    // shows gate truth, this records the skew for the preview banner.
    buildVersion: meta.Version === entry.version ? null : meta.Version,
    Title: meta.Title,
    Description: meta.Description,
    Author: meta.Author,
    Maintainer: meta.Maintainer,
    License: meta.License,
    URL: meta.URL,
    BugReports: meta.BugReports,
    SystemRequirements: meta.SystemRequirements,
    // Single-valued fields arrive as bare strings, not one-element arrays.
    biocViews: meta.biocViews == null ? [] : [].concat(meta.biocViews),
    vignettes: (meta._vignettes ?? []).map((v) => v.filename ?? v.source),
    vignetteTitles: (meta._vignettes ?? []).map((v) => v.title),
    // Trust signals, straight from r-universe. downloads.count is monthly.
    downloads: meta._downloads?.count,
    usedby: meta._usedby,
    stars: meta._stars,
    // Unix seconds of the last upstream commit; rendered as a date, never
    // relative time (build output must not depend on when it was built).
    updated: meta._commit?.time,
  };
  for (const d of meta._dependencies ?? []) {
    const field = ROLE_FIELD[String(d.role ?? '').toLowerCase()];
    if (!field) continue;
    (rec[field] ??= []).push(d.version ? `${d.package} (${d.version})` : d.package);
  }
  return rec;
}

// Worst-first ordering for the check matrix.
const SEVERITY = { ERROR: 0, FAIL: 0, FAILURE: 0, WARNING: 1, NOTE: 2, OK: 3 };
export function severity(check) {
  return SEVERITY[String(check ?? '').toUpperCase()] ?? 3;
}
