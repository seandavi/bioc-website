// node --test src/lib/*.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { transform } from '@astrojs/compiler';

// Astro's compiler mis-nests an <a> whose content mixes text and an expression
// inside a table cell: it re-opens the <a> after </table>, so the rest of the
// page becomes one link (bioc-infrastructure#106, #107).
test('no component re-opens an inline element after </table>', async () => {
  const dir = new URL('../components/', import.meta.url);
  for (const f of readdirSync(dir).filter((f) => f.endsWith('.astro'))) {
    const { code } = await transform(readFileSync(new URL(f, dir), 'utf8'), { filename: f });
    assert.doesNotMatch(code, /<\/table>\s*<(a|b|em|strong|i|code|small|span)\b/, f);
  }
});
