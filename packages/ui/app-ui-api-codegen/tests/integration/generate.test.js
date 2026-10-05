import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import ts from 'typescript';
import { generateContract } from '../../dist/index.js';

function contract() {
  const operation = (tag, name, schema) => ({
    tags: [tag],
    operationId: name,
    responses: {
      200: {
        description: 'OK',
        content: { 'application/json': { schema: { $ref: `#/components/schemas/${schema}` } } }
      }
    }
  });
  return {
    openapi: '3.1.0',
    info: { title: 'Domain test', version: '1' },
    paths: {
      '/resources': { get: operation('library', 'resources', 'Resource') },
      '/audio': { get: operation('audio', 'audio', 'Audio') }
    },
    components: {
      schemas: {
        Resource: {
          type: 'object',
          required: ['id'],
          properties: {
            id: { $ref: '#/components/schemas/Identifier' },
            nested: { $ref: '#/components/schemas/Nested' }
          }
        },
        Audio: {
          type: 'object',
          required: ['id'],
          properties: { id: { $ref: '#/components/schemas/Identifier' } }
        },
        Identifier: { type: 'string' },
        Nested: { type: 'object', properties: { child: { $ref: '#/components/schemas/Nested' } } },
        Unused: { type: 'integer' }
      }
    }
  };
}

function checkTypes(files, assertions) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'app-common-api-types-'));
  try {
    for (const [name, content] of files) fs.writeFileSync(path.join(directory, name), content);
    const entry = path.join(directory, 'assertions.ts');
    fs.writeFileSync(entry, assertions);
    const program = ts.createProgram([entry], {
      strict: true,
      noEmit: true,
      skipLibCheck: false,
      module: ts.ModuleKind.NodeNext,
      moduleResolution: ts.ModuleResolutionKind.NodeNext
    });
    const diagnostics = ts.getPreEmitDiagnostics(program);
    assert.equal(
      diagnostics.length,
      0,
      ts.formatDiagnosticsWithColorAndContext(diagnostics, {
        getCanonicalFileName: (name) => name,
        getCurrentDirectory: () => directory,
        getNewLine: () => '\n'
      })
    );
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
}

test('new tags generate domain files and an aggregate with shared and recursive types', async () => {
  const files = await generateContract(contract());
  assert.deepEqual([...files.keys()].sort(), ['audio.d.ts', 'common.d.ts', 'index.d.ts', 'library.d.ts']);
  assert.match(files.get('common.d.ts'), /Identifier: string/);
  assert.match(files.get('common.d.ts'), /Unused: number/);
  assert.doesNotMatch(files.get('common.d.ts'), /Nested:/);
  assert.match(files.get('library.d.ts'), /CommonComponents\["schemas"\]\["Identifier"\]/);
  checkTypes(
    files,
    `
    import type { paths, components } from './index';
    import type { components as Library } from './library';
    const resource: paths['/resources']['get']['responses'][200]['content']['application/json'] = { id: 'uuid', nested: { child: {} } };
    const audio: paths['/audio']['get']['responses'][200]['content']['application/json'] = { id: 'uuid' };
    const nested: Library['schemas']['Nested'] = { child: {} };
    const unused: components['schemas']['Unused'] = 1;
    // @ts-expect-error response shape must still be enforced
    const invalid: typeof audio = { id: 1 };
    // @ts-expect-error domains must not include unrelated models
    type WrongDomain = Library['schemas']['Audio'];
  `
  );
});

test('removed tags disappear and output is independent of path insertion order', async () => {
  const document = contract();
  const before = await generateContract(document);
  document.paths = Object.fromEntries(Object.entries(document.paths).reverse());
  assert.deepEqual(await generateContract(document), before);
  delete document.paths['/audio'];
  delete document.components.schemas.Audio;
  const after = await generateContract(document);
  assert.ok(!after.has('audio.d.ts'));
  assert.doesNotMatch(after.get('index.d.ts'), /from '.\/audio'/);
  assert.match(after.get('library.d.ts'), /Identifier: string/);
});

test('shared schemas retain their dependency closure', async () => {
  const document = contract();
  document.components.schemas.Identifier = {
    type: 'object',
    properties: { value: { $ref: '#/components/schemas/Nested' } }
  };
  const files = await generateContract(document);
  assert.match(files.get('common.d.ts'), /Nested:/);
  assert.match(files.get('library.d.ts'), /CommonComponents\["schemas"\]\["Nested"\]/);
  checkTypes(
    files,
    `import type { components } from './index'; const id: components['schemas']['Identifier'] = { value: { child: {} } };`
  );
});

test('missing, ambiguous, reserved and unsafe tags fail with the affected route', async () => {
  for (const tags of [undefined, [], ['library', 'audio'], ['common'], ['index'], ['../audio'], ['Audio']]) {
    const document = contract();
    document.paths['/audio'].get.tags = tags;
    await assert.rejects(generateContract(document), /GET \/audio: declare exactly one domain tag/);
  }
});

test('conflicting path ownership, duplicate operations and missing schema references fail', async () => {
  let document = contract();
  document.paths['/audio'].post = { ...document.paths['/resources'].get, operationId: 'create' };
  await assert.rejects(generateContract(document), /all methods on a path must share/);
  document = contract();
  document.paths['/audio'].get.operationId = 'resources';
  await assert.rejects(generateContract(document), /Duplicate operationId/);
  document = contract();
  delete document.components.schemas.Identifier;
  await assert.rejects(generateContract(document), /Missing schema Identifier/);
});

test('empty paths and inline responses without component schemas type-check', async () => {
  const empty = await generateContract({ openapi: '3.1.0', info: { title: 'Empty', version: '1' }, paths: {} });
  assert.deepEqual([...empty.keys()].sort(), ['common.d.ts', 'index.d.ts']);
  checkTypes(empty, `import type { paths } from './index'; const value: paths = {};`);
  const document = contract();
  document.paths = { '/health': { get: { tags: ['health'], operationId: 'health', responses: { 200: { description: 'OK', content: { 'application/json': { schema: { type: 'string' } } } } } } } };
  delete document.components;
  const files = await generateContract(document);
  checkTypes(files, `import type { paths } from './index'; const result: paths['/health']['get']['responses'][200]['content']['application/json'] = 'OK';`);
});

test('schemas referenced by inline non-schema components remain available in every declaration', async () => {
  const document = contract();
  document.components.responses = { SharedResponse: { description: 'OK', content: { 'application/json': { schema: { $ref: '#/components/schemas/Resource' } } } } };
  const files = await generateContract(document);
  checkTypes(files, `import type { components } from './index'; import type { components as Audio } from './audio'; const response: Audio['responses']['SharedResponse']['content']['application/json'] = { id: 'id' }; const shared: components['schemas']['Resource'] = response;`);
});

test('default-field policy is opt-in and aggregate operations preserve method response types', async () => {
  const document = contract();
  document.components.schemas.Resource.properties.enabled = { type: 'boolean', default: true };
  const ordinary = await generateContract(document);
  const legacy = await generateContract(document, { defaultNonNullable: true });
  checkTypes(ordinary, `import type { components } from './index'; const item: components['schemas']['Resource'] = { id: 'id' };`);
  checkTypes(legacy, `
    import type { components, operations } from './index';
    const item: components['schemas']['Resource'] = { id: 'id', enabled: true };
    const response: operations['resources']['responses'][200]['content']['application/json'] = item;
    // @ts-expect-error legacy default fields remain required
    const missing: components['schemas']['Resource'] = { id: 'id' };
    // @ts-expect-error aggregate operations still enforce the domain response shape
    const invalid: operations['audio']['responses'][200]['content']['application/json'] = { id: 1 };
  `);
});
