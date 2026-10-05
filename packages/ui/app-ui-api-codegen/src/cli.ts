#!/usr/bin/env node
import fs from 'node:fs/promises';
import { parseArgs } from 'node:util';
import { generateContract, writeContract, type OpenAPI3 } from './index.js';

try {
  const { values } = parseArgs({ options: {
    input: { type: 'string' }, output: { type: 'string' },
    check: { type: 'boolean', default: false }, help: { type: 'boolean', short: 'h' }
  }});
  if (values.help) {
    console.log('Usage: app-common-gen-api --input <openapi.json|URL> --output <generated-directory> [--check]');
  } else {
    if (!values.input || !values.output) throw new Error('--input and --output are required. Use --help for usage.');
    let source: string;
    if (/^https?:\/\//.test(values.input)) {
      const response = await fetch(values.input, { signal: AbortSignal.timeout(30_000) });
      if (!response.ok) throw new Error(`OpenAPI fetch failed: HTTP ${response.status}`);
      source = await response.text();
    } else {
      source = await fs.readFile(values.input, 'utf8');
    }
    const files = await generateContract(JSON.parse(source) as OpenAPI3);
    writeContract(files, values.output, { check: values.check });
    console.log(values.check ? 'API contracts are up to date.' : `Generated ${files.size} API contract files from domain tags.`);
  }
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}
