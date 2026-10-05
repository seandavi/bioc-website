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
