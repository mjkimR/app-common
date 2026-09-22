import assert from 'node:assert/strict';
import { test } from 'node:test';
import { structure } from '../../structure.js';

test('rejects unbounded, undocumented, broad, and duplicate exceptions', () => {
  const valid = { file: 'src/lib/Form.svelte', max: 550, reason: 'Cohesive form.' };
  for (const max of [Infinity, NaN, 550.5, '550', 0, 500]) {
    assert.throws(() => structure({ exceptions: [{ ...valid, max }] }), /finite integer/);
  }
  for (const reason of ['', '  ', undefined]) {
    assert.throws(() => structure({ exceptions: [{ ...valid, reason }] }), /requires a reason/);
  }
  for (const file of ['src/**/*.svelte', '/src/Form.svelte', 'src/../Form.svelte', 'src//Form.svelte']) {
    assert.throws(() => structure({ exceptions: [{ ...valid, file }] }), /exact src\//);
  }
  assert.throws(() => structure({ exceptions: [valid, valid] }), /Duplicate/);
});
