import assert from 'node:assert/strict';
import { execFile, spawnSync } from 'node:child_process';
import { createServer } from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';
import { generateContract, writeContract } from '../../dist/index.js';

const cli = fileURLToPath(new URL('../../dist/cli.js', import.meta.url));
const document = {
  openapi: '3.1.0', info: { title: 'CLI fixture', version: '1' },
  paths: { '/health': { get: { tags: ['health'], operationId: 'health', responses: { 200: { description: 'OK' } } } } }
};

test('CLI generates, checks without writes, reports drift and removes owned stale files', (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'app-common-api-cli-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const input = path.join(root, 'openapi.json');
  const output = path.join(root, 'generated');
  fs.writeFileSync(input, JSON.stringify(document));
  const run = (...args) => {
    const result = spawnSync(process.execPath, [cli, '--input', input, '--output', output, ...args], { encoding: 'utf8' });
    assert.ifError(result.error);
    return result;
  };
  assert.equal(run('--check').status, 1);
  assert.ok(!fs.existsSync(output));
  assert.equal(run().status, 0);
  assert.deepEqual(fs.readdirSync(output).sort(), ['common.d.ts', 'health.d.ts', 'index.d.ts']);
  const health = path.join(output, 'health.d.ts');
  const mtime = fs.statSync(health).mtimeMs;
  fs.writeFileSync(path.join(output, 'README.md'), 'Keep me');
  fs.writeFileSync(path.join(output, 'custom.d.ts'), 'export type Custom = string;');
  assert.equal(run('--check').status, 0);
  assert.equal(fs.statSync(health).mtimeMs, mtime);
  fs.writeFileSync(health, fs.readFileSync(health, 'utf8').replace(/\n/g, '\r\n'));
  assert.equal(run('--check').status, 0);
  const next = structuredClone(document);
  next.paths['/health'].get.tags = ['status'];
  fs.writeFileSync(input, JSON.stringify(next));
  const stale = run('--check');
  assert.equal(stale.status, 1);
  assert.match(stale.stderr, /out of date.*health.d.ts/);
  assert.ok(fs.existsSync(health));
  assert.equal(run().status, 0);
  assert.ok(!fs.existsSync(health));
  assert.equal(fs.readFileSync(path.join(output, 'README.md'), 'utf8'), 'Keep me');
  assert.ok(fs.existsSync(path.join(output, 'custom.d.ts')));
  assert.equal(run('--check').status, 0);
});

test('output refuses unowned collisions and symlinks before making changes', async (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'app-common-api-output-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const files = await generateContract(document);
  const target = path.join(root, 'health.d.ts');
  fs.writeFileSync(target, 'manual');
  assert.throws(() => writeContract(files, root), /unowned file health.d.ts/);
  assert.equal(fs.readFileSync(target, 'utf8'), 'manual');
  assert.ok(!fs.existsSync(path.join(root, 'common.d.ts')));
  fs.unlinkSync(target);
  const outside = path.join(root, 'outside.txt');
  fs.writeFileSync(outside, 'manual');
  fs.symlinkSync(outside, target);
  assert.throws(() => writeContract(files, root), /unowned file health.d.ts/);
  assert.equal(fs.readFileSync(outside, 'utf8'), 'manual');
});

test('CLI rejects invalid inputs and options without creating output', (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'app-common-api-invalid-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const input = path.join(root, 'invalid.json');
  const output = path.join(root, 'generated');
  fs.writeFileSync(input, '{');
  assert.equal(spawnSync(process.execPath, [cli, '--input', input, '--output', output]).status, 1);
  assert.ok(!fs.existsSync(output));
  assert.equal(spawnSync(process.execPath, [cli, '--unknown']).status, 1);
  assert.equal(spawnSync(process.execPath, [cli]).status, 1);
  assert.equal(spawnSync(process.execPath, [cli, '--help']).status, 0);
});

test('CLI accepts an HTTP schema and fails on HTTP errors', async (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'app-common-api-http-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const server = createServer((request, response) => {
    if (request.url !== '/openapi.json') {
      response.writeHead(503).end('Unavailable');
      return;
    }
    response.setHeader('Content-Type', 'application/json');
    response.end(JSON.stringify(document));
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise((resolve) => server.close(resolve)));
  const url = `http://127.0.0.1:${server.address().port}`;
  const run = promisify(execFile);
  const output = path.join(root, 'generated');
  await run(process.execPath, [cli, '--input', `${url}/openapi.json`, '--output', output]);
  assert.ok(fs.existsSync(path.join(output, 'health.d.ts')));
  await assert.rejects(run(process.execPath, [cli, '--input', `${url}/error`, '--output', output]), /HTTP 503/);
});

test('CLI default-field flag preserves the previous openapi-typescript policy', (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'app-common-api-defaults-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const input = path.join(root, 'openapi.json');
  const schema = structuredClone(document);
  schema.components = { schemas: { Health: { type: 'object', properties: { enabled: { type: 'boolean', default: true } } } } };
  schema.paths['/health'].get.responses = { 200: { description: 'OK', content: { 'application/json': { schema: { $ref: '#/components/schemas/Health' } } } } };
  fs.writeFileSync(input, JSON.stringify(schema));
  for (const [mode, args] of [['ordinary', []], ['legacy', ['--default-non-nullable']]]) {
    const output = path.join(root, mode);
    const result = spawnSync(process.execPath, [cli, '--input', input, '--output', output, ...args], { encoding: 'utf8' });
    assert.ifError(result.error);
    assert.equal(result.status, 0, result.stderr);
    assert.match(fs.readFileSync(path.join(output, 'health.d.ts'), 'utf8'), mode === 'ordinary' ? /enabled\?: boolean/ : /enabled: boolean/);
  }
});
