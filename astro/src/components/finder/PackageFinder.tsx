/**
 * The package finder: the interactive heart of the BiocViews page.
 *
 * Search-first, designed for the job (finding packages) rather than for
 * parity with the legacy jsTree widget: one box matches package names,
 * titles, and category terms; the category tree is facet navigation; results
 * are a table with repo badges. The `#___Term` deep-link contract from the
 * legacy site is preserved (read on load, written on selection).
 *
 * This is deliberately the site's only hydrated island (plus whatever earns
 * it next): pages where interactivity IS the content. Everything else stays
 * static HTML. Markup uses the vendored legacy classes so the skin is
 * inherited, not reinvented.
 */
import { useEffect, useMemo, useState } from 'react';

export type TreeTerm = {
  data: string;
  attr?: { id?: string; packageList?: string };
  children?: TreeTerm[];
};

type Term = {
  id: string;
  name: string;
  count: number;
  children: Term[];
  all: string[]; // cumulative package names over the subtree
};

type Props = {
  version: string;
  channel: string | null;
  other: { version: string; channel: string } | null;
  roots: TreeTerm[];
  /** name -> [repoPath, title] */
  pkgs: Record<string, [string, string]>;
};

const REPO_BADGE: Record<string, string> = {
  bioc: 'Software',
  'data/annotation': 'Annotation',
  'data/experiment': 'Experiment',
  workflows: 'Workflow',
};

function build(node: TreeTerm): Term {
  const label = String(node.data ?? '');
  const m = label.match(/^(.*?)\s*\((\d+)\)\s*$/);
  const children = (node.children ?? []).map(build);
  const direct = node.attr?.packageList ? node.attr.packageList.split(',').filter(Boolean) : [];
  const all = [...new Set([...direct, ...children.flatMap((c) => c.all)])];
  return {
    id: node.attr?.id ?? (m ? m[1] : label),
    name: m ? m[1] : label,
    count: m ? Number(m[2]) : all.length,
    children,
    all,
  };
}

function flatten(terms: Term[], into: Map<string, Term> = new Map()): Map<string, Term> {
  for (const t of terms) {
    into.set(t.id, t);
    flatten(t.children, into);
  }
  return into;
}

const PAGE = 100;

export default function PackageFinder({ version, channel, other, roots, pkgs }: Props) {
  const terms = useMemo(() => roots.map(build), [roots]);
  const byId = useMemo(() => flatten(terms), [terms]);
  const allNames = useMemo(() => Object.keys(pkgs).sort((a, b) => a.localeCompare(b)), [pkgs]);

  const [active, setActive] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [limit, setLimit] = useState(PAGE);
  const [open, setOpen] = useState<Set<string>>(() => new Set(terms.map((t) => t.id)));

  // The static no-JS tree is the fallback; hide it once the island is live.
  useEffect(() => {
    document.getElementById('bv-fallback')?.setAttribute('hidden', '');
  }, []);

  // #___Term contract: honor on load and on external hash changes; write on
  // selection so links to the current view keep working.
  useEffect(() => {
    const read = () => {
      const id = decodeURIComponent(location.hash.replace(/^#___/, ''));
      if (id && byId.has(id)) select(id, { fromHash: true });
    };
    read();
    addEventListener('hashchange', read);
    return () => removeEventListener('hashchange', read);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [byId]);

  function select(id: string | null, opts: { fromHash?: boolean } = {}) {
    setActive(id);
    setLimit(PAGE);
    if (id) {
      // open the path to the selection
      setOpen((prev) => {
        const next = new Set(prev);
        const path = (ts: Term[], trail: string[]): string[] | null => {
          for (const t of ts) {
            if (t.id === id) return [...trail, t.id];
            const found = path(t.children, [...trail, t.id]);
            if (found) return found;
          }
          return null;
        };
        for (const p of path(terms, []) ?? []) next.add(p);
        return next;
      });
      if (!opts.fromHash) history.replaceState(null, '', `#___${id}`);
    } else if (!opts.fromHash) {
      history.replaceState(null, '', location.pathname);
    }
  }

  const q = query.trim().toLowerCase();
  const activeTerm = active ? byId.get(active) : undefined;

  const termHits = useMemo(() => {
    if (!q) return [];
    return [...byId.values()]
      .filter((t) => t.name.toLowerCase().includes(q))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [q, byId]);

  const results = useMemo(() => {
    const base = activeTerm ? activeTerm.all.slice().sort((a, b) => a.localeCompare(b)) : allNames;
    if (!q) return base;
    const starts: string[] = [];
    const contains: string[] = [];
    const titled: string[] = [];
    for (const n of base) {
      const nl = n.toLowerCase();
      if (nl.startsWith(q)) starts.push(n);
      else if (nl.includes(q)) contains.push(n);
      else if ((pkgs[n]?.[1] ?? '').toLowerCase().includes(q)) titled.push(n);
    }
    return [...starts, ...contains, ...titled];
  }, [q, activeTerm, allNames, pkgs]);

  const TermRow = ({ t, depth }: { t: Term; depth: number }) => (
    <li>
      <div className={`bvf-term${t.id === active ? ' bvf-active' : ''}`} style={{ paddingLeft: `${depth * 0.9}rem` }}>
        {t.children.length > 0 ? (
          <button
            type="button"
            className="bvf-chevron"
            aria-expanded={open.has(t.id)}
            aria-label={`${open.has(t.id) ? 'Collapse' : 'Expand'} ${t.name}`}
            onClick={() =>
              setOpen((prev) => {
                const next = new Set(prev);
                next.has(t.id) ? next.delete(t.id) : next.add(t.id);
                return next;
              })
            }
          >
            {open.has(t.id) ? '▾' : '▸'}
          </button>
        ) : (
          <span className="bvf-chevron bvf-chevron-none" />
        )}
        <button type="button" className="bvf-name" onClick={() => select(t.id === active ? null : t.id)}>
          {t.name} <span className="bvf-count">({t.count})</span>
        </button>
      </div>
      {t.children.length > 0 && open.has(t.id) && (
        <ul>
          {t.children.map((c) => (
            <TermRow key={c.id} t={c} depth={depth + 1} />
          ))}
        </ul>
      )}
    </li>
  );

  const shown = results.slice(0, limit);
  const heading = activeTerm
    ? `${activeTerm.name} — ${results.length} package${results.length === 1 ? '' : 's'}`
    : q
      ? `${results.length} package${results.length === 1 ? '' : 's'}`
      : `All packages — ${results.length}`;

  return (
    <div id="bvf">
      <div className="bvf-topbar">
        <p className="format-bold">
          Bioconductor {version}
          {channel && ` (${channel === 'release' ? 'Release' : 'Devel'})`}
        </p>
        {other && (
          <a className="brand-border-button" href={`/packages/${other.version}/BiocViews.html#___Software`}>
            <span className="span-brand format-bold">
              Go to {other.version} ({other.channel === 'devel' ? 'Devel' : 'Release'})
            </span>
          </a>
        )}
      </div>

      <div className="bvf-search">
        <label htmlFor="bvf-q" className="sr-only">
          Search packages and categories
        </label>
        <input
          id="bvf-q"
          className="package-input"
          type="search"
          autoComplete="off"
          placeholder="Search packages by name, title, or category…"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setLimit(PAGE);
          }}
        />
      </div>

      {q && termHits.length > 0 && (
        <div className="bvf-cats">
          <span>Categories:</span>
          {termHits.map((t) => (
            <button
              key={t.id}
              type="button"
              className="bvf-chip"
              onClick={() => {
                select(t.id);
                setQuery('');
              }}
            >
              {t.name} <span className="bvf-count">({t.count})</span>
            </button>
          ))}
        </div>
      )}

      <div className="bvf-columns">
        <nav className="bvf-tree" aria-label="Package categories">
          <div className={`bvf-term${active === null ? ' bvf-active' : ''}`}>
            <span className="bvf-chevron bvf-chevron-none" />
            <button type="button" className="bvf-name" onClick={() => select(null)}>
              All packages <span className="bvf-count">({allNames.length})</span>
            </button>
          </div>
          <ul>
            {terms.map((t) => (
              <TermRow key={t.id} t={t} depth={0} />
            ))}
          </ul>
        </nav>

        <section className="bvf-results" aria-live="polite">
          <h2 className="bvf-heading">
            {heading}
            {q && ` matching “${query.trim()}”`}
            {activeTerm && (
              <button type="button" className="bvf-clear" onClick={() => select(null)}>
                clear
              </button>
            )}
          </h2>
          <table>
            <thead>
              <tr>
                <th>Package</th>
                <th>Title</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((n) => {
                const [repo, title] = pkgs[n] ?? ['bioc', ''];
                return (
                  <tr key={n}>
                    <td className="bvf-pkg">
                      <a href={`/packages/${version}/${repo}/html/${n}.html`}>{n}</a>
                      <span className={`bvf-badge bvf-badge-${repo.replace(/\W/g, '-')}`}>
                        {REPO_BADGE[repo] ?? repo}
                      </span>
                    </td>
                    <td>{title}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {results.length > limit && (
            <button type="button" className="brand-border-button bvf-more" onClick={() => setLimit(limit + PAGE)}>
              <span className="span-brand format-bold">
                Show {Math.min(PAGE, results.length - limit)} more of {results.length - limit}
              </span>
            </button>
          )}
        </section>
      </div>
    </div>
  );
}
