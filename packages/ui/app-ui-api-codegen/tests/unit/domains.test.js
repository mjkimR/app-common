import assert from 'node:assert/strict';
import test from 'node:test';
import { partition } from '../../dist/domains.js';

const document = () => ({
  openapi: '3.1.0', info: { title: 'Partition', version: '1' },
  paths: { '/health': { get: { tags: ['health'], operationId: 'health', responses: {} } } }
});

test('missing operation IDs, unsupported refs and Windows device filenames fail', () => {
  let input = document();
  delete input.paths['/health'].get.operationId;
  assert.throws(() => partition(input), /GET \/health: missing operationId/);
  input = document();
  input.paths['/health'].get.responses = { 200: { $ref: '#/components/responses/Result' } };
  assert.throws(() => partition(input), /Unsupported reference/);
  for (const tag of ['con', 'nul', 'com1', 'lpt9']) {
    input = document();
    input.paths['/health'].get.tags = [tag];
    assert.throws(() => partition(input), /reserved/);
  }
});

test('path references, webhooks and $defs fail instead of losing declarations', () => {
  const input = document();
  input.paths['/health'] = { $ref: '#/components/pathItems/Health' };
  assert.throws(() => partition(input), /Unsupported path reference/);
  assert.throws(() => partition({ ...document(), webhooks: { event: {} } }), /Webhooks/);
  assert.throws(() => partition({ ...document(), $defs: { Model: {} } }), /\$defs/);
});
