import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

// The contract shared with the Nanoc build: an object keyed by package name,
// one file per version per repo. See docs/views-and-r-universe.qmd.
//
// Versions and repos are discovered from the data directory rather than listed,
// because the set genuinely varies: JSON exists from 2.5 onward, and workflows
// only appear at 3.7. Hardcoding it would silently drop releases.
export const REPOS = ['bioc', 'data/annotation', 'data/experiment', 'workflows'];

// Resolve from the project root, not import.meta.url — Vite rewrites module
// URLs during the build, which silently broke path resolution here.
const DATA = join(process.cwd(), 'data');

// Sorted numerically so build output order is stable across runs.
export function versions() {
  return readdirSync(DATA, { withFileTypes: true })
    .filter((d) => d.isDirectory() && /^\d+\.\d+$/.test(d.name))
    .map((d) => d.name)
    .sort((a, b) => {
      const [am, an] = a.split('.').map(Number);
      const [bm, bn] = b.split('.').map(Number);
      return am - bm || an - bn;
    });
}

// Only the repos that actually exist for a given release.
export function reposFor(version) {
  return REPOS.filter((r) => existsSync(join(DATA, version, r, 'packages.json')));
}

export function loadRepo(version, repo) {
  const f = join(DATA, version, repo, 'packages.json');
  // Fail loudly: a missing data file must not silently yield zero pages.
  if (!existsSync(f)) throw new Error(`missing package data: ${f}`);
  return JSON.parse(readFileSync(f, 'utf8'));
}

// Dependency strings carry version constraints ("R (>= 3.6.0)"); the display
// name is everything before the first space or paren.
export function depName(entry) {
  return String(entry).split(/[ (]/)[0];
}

// The packages shipped with R itself (plus "R" in Depends): no page anywhere.
const BASE_R = new Set([
  'R', 'base', 'compiler', 'datasets', 'graphics', 'grDevices', 'grid', 'methods',
  'parallel', 'splines', 'stats', 'stats4', 'tcltk', 'tools', 'utils',
]);

// version -> Map(package name -> repo) over every repo of that release, so a
// dependency can be told apart as Bioconductor (and which repo) or not.
const biocRepos = new Map();
function biocRepoOf(version, name) {
  if (!biocRepos.has(version)) {
    const m = new Map();
    for (const repo of reposFor(version)) {
      for (const n of Object.keys(loadRepo(version, repo))) m.set(n, repo);
    }
    biocRepos.set(version, m);
  }
  return biocRepos.get(version).get(name);
}

// Where a dependency entry points: its Bioconductor page in this release,
// CRAN for anything else (reverse dependencies include CRAN packages, which
// pipeline/packages.py folds into the reverse graph), or null for base R.
export function depHref(version, entry) {
  const name = depName(entry);
  if (BASE_R.has(name)) return null;
  const repo = biocRepoOf(version, name);
  if (repo) return `/packages/${version}/${repo}/html/${name}.html`;
  return `https://cran.r-project.org/package=${name}`;
}

export function asArray(v) {
  if (v == null) return [];
  return Array.isArray(v) ? v : [v];
}

// Human label for a repository, as the index page headings and breadcrumbs use.
const LABELS = {
  'bioc': 'Software',
  'data/annotation': 'Annotation',
  'data/experiment': 'Experiment Data',
  'workflows': 'Workflow',
};
export function repoLabel(repo) {
  return LABELS[repo] ?? repo;
}

// tree.json drives the category browser. Unlike packages.json its absence is
// not an error -- it is generated per release and older releases may not have
// one yet -- so this returns null rather than throwing, and the caller skips
// emitting a BiocViews page for that version.
export function loadTree(version) {
  const f = join(DATA, version, 'tree.json');
  if (!existsSync(f)) return null;
  return JSON.parse(readFileSync(f, 'utf8'));
}

// "BioC 2.14 (R-3.1) (12 years)" from a record's `since` field (pipeline/since.py).
// Whole years since the release date, counted at build time; a release with no
// date (devel) gets none.
export function sinceLabel({ release, r, date, orEarlier }, now = new Date()) {
  let label = `BioC ${release}${orEarlier ? ' or earlier' : ''} (R-${r})`;
  if (date) {
    const d = new Date(date);
    let years = now.getUTCFullYear() - d.getUTCFullYear();
    if (now.getUTCMonth() < d.getUTCMonth() || (now.getUTCMonth() === d.getUTCMonth() && now.getUTCDate() < d.getUTCDate())) years--;
    label += years < 1 ? ' (less than a year)' : ` (${years} ${years === 1 ? 'year' : 'years'})`;
  }
  return label;
}

// This package in every release that ships it, as [{ version, repo, channel }]
// newest first, so a package page can link to its siblings and every link
// resolves. `channel` is 'devel' for the newest release on disk and 'release'
// for its predecessor (as in pages/packages/[...slug].astro).
//
// The list comes from the record's `releases` field ([[version, repo], ...],
// written by the pipeline, which sees every release). CI builds from a snapshot
// holding only the two live releases, so walking the disk there would never
// reach the old versions. The walk remains as the fallback for a record without
// the field (a stale snapshot) and for malformed values.
let releasesOf;
export function releasesOfPackage(name, pkg) {
  const live = versions().reverse();
  const channelOf = (v) => (v === live[0] ? 'devel' : v === live[1] ? 'release' : null);
  let list = (Array.isArray(pkg?.releases) ? pkg.releases : [])
    .filter((e) => Array.isArray(e) && /^\d+\.\d+$/.test(e[0]) && typeof e[1] === 'string')
    .map(([version, repo]) => ({ version, repo }));
  if (list.length === 0) {
    if (!releasesOf) {
      releasesOf = new Map();
      for (const version of live) {
        for (const repo of reposFor(version)) {
          for (const n of Object.keys(loadRepo(version, repo))) {
            if (!releasesOf.has(n)) releasesOf.set(n, []);
            releasesOf.get(n).push({ version, repo });
          }
        }
      }
    }
    list = releasesOf.get(name) ?? [];
  }
  // One entry per version: a name in two repos of one release lists it once.
  const seen = new Set();
  return list
    .filter((r) => !seen.has(r.version) && seen.add(r.version))
    .map((r) => ({ ...r, channel: channelOf(r.version) }));
}
