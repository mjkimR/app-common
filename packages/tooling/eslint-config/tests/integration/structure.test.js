import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ESLint } from 'eslint';
import { structure } from '../../structure.js';

const source = (lines, svelte = false) =>
  Array(lines).fill(svelte ? '<div>content</div>' : 'void 0;').join('\n') + '\n';

async function lint(filePath, text, options = {}) {
  const eslint = new ESLint({ overrideConfigFile: true, overrideConfig: structure(options) });
  return (await eslint.lintText(text, { filePath }))[0];
}

for (const [file, max] of [
  ['src/lib/View.svelte', 500],
  ['src/lib/state.svelte.ts', 400],
  ['src/lib/helpers.ts', 400],
  ['src/routes/+page.svelte', 200],
  ['src/routes/+page.ts', 200]
]) {
  test(`${file}: accepts the limit and fails one line over it`, async () => {
    const svelte = file.endsWith('.svelte');
    assert.deepEqual((await lint(file, source(max, svelte))).messages, []);
    const result = await lint(file, source(max + 1, svelte));
    assert.equal(result.errorCount, 1);
    assert.equal(result.warningCount, 0);
    assert.equal(result.messages[0].ruleId, 'max-lines');
  });
}

test('blank lines and standalone JS/TS comments do not consume the budget', async () => {
  const ts = '// comment\n\n/* multiline\ncomment */\n' + source(400);
  assert.deepEqual((await lint('src/lib/helpers.ts', ts)).messages, []);
  const svelte = '<script lang="ts">\n// comment\n/* multiline\ncomment */\n</script>\n\n' + source(498, true);
  assert.deepEqual((await lint('src/lib/View.svelte', svelte)).messages, []);
});

test('HTML and CSS comments count as markup/style under the core max-lines rule', async () => {
  const html = '<!-- comment -->\n' + source(500, true);
  assert.equal((await lint('src/lib/View.svelte', html)).errorCount, 1);
  const css = '<style>\n/* comment */\n</style>\n' + source(498, true);
  assert.equal((await lint('src/lib/View.svelte', css)).errorCount, 1);
});

test('parses Svelte 5 runes and TypeScript scripts', async () => {
  const text = '<script lang="ts">\nlet count: number = $state(0);\n</script>\n<p>{count}</p>\n';
  assert.deepEqual((await lint('src/lib/Counter.svelte', text)).messages, []);
});

test('a bounded exception is quiet until its own limit is exceeded', async () => {
  const file = 'src/lib/Form.svelte';
  const options = { exceptions: [{ file, max: 550, reason: 'One cohesive form; keep fields together.' }] };
  assert.deepEqual((await lint(file, source(540, true), options)).messages, []);
  assert.deepEqual((await lint(file, source(550, true), options)).messages, []);
  const grown = await lint(file, source(551, true), options);
  assert.equal(grown.errorCount, 1);
  assert.equal(grown.messages[0].ruleId, 'max-lines');
  assert.equal((await lint('src/lib/Other.svelte', source(501, true), options)).errorCount, 1);
});

test('exact route exceptions support SvelteKit parameters and route groups', async () => {
  const file = 'src/routes/(app)/projects/[id]/+page.svelte';
  const options = { exceptions: [{ file, max: 230, reason: 'Route-specific composition.' }] };
  assert.deepEqual((await lint(file, source(230, true), options)).messages, []);
  assert.equal((await lint(file, source(231, true), options)).errorCount, 1);
  assert.equal((await lint('src/routes/(app)/projects/i/+page.svelte', source(201, true), options)).errorCount, 1);
});

test('tests and declarations are excluded; authored UI is checked unless explicitly excluded', async () => {
  for (const file of ['src/lib/thing.test.ts', 'src/lib/View.svelte.spec.ts', 'src/lib/api/schema.d.ts']) {
    const result = await lint(file, source(600));
    assert.equal(result.errorCount, 0);
    assert.equal(result.messages.some((m) => m.ruleId === 'max-lines'), false);
  }
  const file = 'src/lib/components/ui/Button.svelte';
  assert.equal((await lint(file, source(501, true))).errorCount, 1);
  const ignored = await lint(file, source(501, true), { ignores: ['src/lib/components/ui/**'] });
  assert.equal(ignored.errorCount, 0);
  assert.equal(ignored.messages.some((m) => m.ruleId === 'max-lines'), false);
});
