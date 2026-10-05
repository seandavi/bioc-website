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

// The author part of the generated citation. R's citation() names the
// Authors@R people with role "aut"; the data contract carries only the Author
// field, so rebuild that list from it: split on commas outside [roles] and
// (comments), keep the "aut" entries when roles are present (else everyone),
// drop roles, comments and e-mail addresses. Names stay as written: no guessing
// at family/given order. A few packages paste Authors@R source into Author;
// that is not a name list, so it yields nothing.
export function citationAuthors(author = '') {
  if (/\bperson\(/.test(author)) return '';
  const people = [];
  let depth = 0;
  let cur = '';
  for (const ch of author) {
    if (ch === '[' || ch === '(') depth++;
    else if (ch === ']' || ch === ')') depth = Math.max(0, depth - 1);
    if (ch === ',' && !depth) { people.push(cur); cur = ''; } else cur += ch;
  }
  people.push(cur);
  const aut = people.filter((p) => /\[[^\]]*\baut\b/.test(p));
  return (aut.length ? aut : people)
    .map((p) => {
      // Innermost groups first, so nested comments go whole; whatever is left
      // unbalanced is cut at its first opener.
      let prev;
      do {
        prev = p;
        p = p.replace(/\([^()]*\)|\[[^\[\]]*\]|<[^<>]*>/g, '');
      } while (p !== prev);
      return p.split(/[\[(<]/)[0].replace(/\s*\S*@\S*/g, '').replace(/\s+/g, ' ').trim();
    })
    .filter(Boolean).join(', ').replace(/\.+$/, '');
}
