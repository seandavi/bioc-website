// node --test src/lib/*.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { splitUrls, personParts } from './packages.js';

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
