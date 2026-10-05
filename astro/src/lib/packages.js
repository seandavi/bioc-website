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
