// node --test src/lib/*.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { splitUrls, personParts, sinceLabel } from './packages.js';

test('splitUrls: one URL per comma, space or newline (bioc-infrastructure#100)', () => {
  assert.deepEqual(splitUrls('https://bioinf.wehi.edu.au/edgeR/, https://bioconductor.org/packages/edgeR'),
    ['https://bioinf.wehi.edu.au/edgeR/', 'https://bioconductor.org/packages/edgeR']);
  assert.deepEqual(splitUrls('https://a.org\nhttps://b.org https://c.org,https://d.org'),
    ['https://a.org', 'https://b.org', 'https://c.org', 'https://d.org']);
  assert.deepEqual(splitUrls('https://a.org'), ['https://a.org']);
  assert.deepEqual(splitUrls(undefined), []);
});

test('personParts: ORCID annotations become links, emails are obfuscated', () => {
  assert.deepEqual(
    personParts('Mukai Wang [aut, cre] (ORCID: <https://orcid.org/0000-0002-1413-1904>), Gen Li [aut]'),
    ['Mukai Wang [aut, cre] ', { orcid: 'https://orcid.org/0000-0002-1413-1904', id: '0000-0002-1413-1904' }, ', Gen Li [aut]']);
  assert.deepEqual(personParts('A B (<https://orcid.org/0000-0001>)'),
    ['A B ', { orcid: 'https://orcid.org/0000-0001', id: '0000-0001' }]);
  assert.deepEqual(personParts('Yunshun Chen <yuchen@wehi.edu.au>, Gordon Smyth <smyth@wehi.edu.au>'),
    ['Yunshun Chen ', '<yuchen at wehi.edu.au>', ', Gordon Smyth ', '<smyth at wehi.edu.au>']);
  assert.deepEqual(personParts('Marc Carlson'), ['Marc Carlson']);
});

test('sinceLabel: the legacy format, half years, "or earlier" and "> " together (bioc-infrastructure#107)', () => {
  const now = new Date('2026-10-08T12:00:00Z');
  assert.equal(sinceLabel({ release: '1.6', r: '2.1', date: '2005-05-18', orEarlier: true }, now),
    'BioC 1.6 (R-2.1) or earlier (> 21.5 years)');
  assert.equal(sinceLabel({ release: '2.3', r: '2.8', date: '2008-10-22' }, now), 'BioC 2.3 (R-2.8) (18 years)');
  assert.equal(sinceLabel({ release: '2.12', r: '3.0', date: '2013-04-04' }, now), 'BioC 2.12 (R-3.0) (13.5 years)');
  assert.equal(sinceLabel({ release: '3.21', r: '4.5', date: '2025-04-16' }, now), 'BioC 3.21 (R-4.5) (1.5 years)');
  assert.equal(sinceLabel({ release: '3.22', r: '4.5', date: '2025-10-30' }, now), 'BioC 3.22 (R-4.5) (1 year)');
  assert.equal(sinceLabel({ release: '3.23', r: '4.6', date: '2026-04-29' }, now), 'BioC 3.23 (R-4.6) (< 6 months)');
  assert.equal(sinceLabel({ release: '3.24', r: '4.6' }, now), 'BioC 3.24 (R-4.6)');
});
