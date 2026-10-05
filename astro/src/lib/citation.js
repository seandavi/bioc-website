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
    if ((ch === ',' || ch === ';') && !depth) { people.push(cur); cur = ''; } else cur += ch;
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
    .filter(Boolean).join(', ').replace(/\s+([.,])/g, '$1').replace(/\.+$/, '').trim();
}

// The citation fragment comes from the mirror, but its text is written by package
// maintainers (inst/CITATION), so keep only the markup R's citation HTML uses:
// a tag allowlist, no attributes except an http(s) href on links.
const KEEP = new Set(['P', 'EM', 'STRONG', 'B', 'I', 'A', 'BR', 'CODE', 'SUP', 'SUB']);
export function sanitizeCitation(root) {
  for (const el of root.querySelectorAll('*')) {
    if (!KEEP.has(el.tagName)) { el.remove(); continue; }
    for (const { name, value } of [...el.attributes]) {
      if (!(el.tagName === 'A' && name === 'href' && /^https?:\/\//i.test(value))) el.removeAttribute(name);
    }
  }
}
