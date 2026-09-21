import tsParser from '@typescript-eslint/parser';
import svelteParser from 'svelte-eslint-parser';

const limits = { svelte: 500, typescript: 400, routes: 200 };
/** @param {number} max @returns {import('eslint').Linter.RuleEntry} */
const maxLines = (max) => ['error', { max, skipBlankLines: true, skipComments: true }];

/**
 * File-size checks for authored source, relative to the consumer's ESLint config.
 * Add alongside correctness rules or use alone for a quick structure check.
 *
 * @param {{ ignores?: string[], exceptions?: { file: string, max: number, reason: string }[] }} options
 * @returns {import('eslint').Linter.Config[]}
 */
export function structure({ ignores = [], exceptions = [] } = {}) {
  const excluded = ['**/*.{test,spec}.*', '**/*.d.ts', ...ignores];
  const seen = new Set();
  const overrides = exceptions.map(({ file, max, reason }) => {
    // Exceptions identify one source file, never a directory or glob.
    if (
      typeof file !== 'string' ||
      !/^src\/.+\.(?:ts|svelte)$/.test(file) ||
      /[\\*?{}!]/.test(file) ||
      file.split('/').some((part) => !part || part === '.' || part === '..')
    ) {
      throw new Error(`File-size exception requires an exact src/ path: ${file}`);
    }
    if (seen.has(file)) throw new Error(`Duplicate file-size exception: ${file}`);
    seen.add(file);
    if (typeof reason !== 'string' || !reason.trim()) {
      throw new Error(`File-size exception requires a reason: ${file}`);
    }
    const baseline = file.startsWith('src/routes/')
      ? limits.routes
      : file.endsWith('.svelte')
        ? limits.svelte
        : limits.typescript;
    if (!Number.isSafeInteger(max) || max <= baseline) {
      throw new Error(`File-size exception requires a finite integer above ${baseline}: ${file}`);
    }
    return {
      name: `app-common/structure/exception: ${file} (${reason.trim()})`,
      files: [file.replace(/[\[\]()]/g, '\\$&')],
      ignores: excluded,
      rules: { 'max-lines': maxLines(max) }
    };
  });

  return [
    {
      name: 'app-common/structure/typescript',
      files: ['src/**/*.ts'],
      ignores: excluded,
      languageOptions: { parser: tsParser },
      rules: { 'max-lines': maxLines(limits.typescript) }
    },
    {
      name: 'app-common/structure/svelte',
      files: ['src/**/*.svelte'],
      ignores: excluded,
      languageOptions: { parser: svelteParser, parserOptions: { parser: tsParser } },
      rules: { 'max-lines': maxLines(limits.svelte) }
    },
    {
      name: 'app-common/structure/routes',
      files: ['src/routes/**/*.{ts,svelte}'],
      ignores: excluded,
      rules: { 'max-lines': maxLines(limits.routes) }
    },
    ...overrides
  ];
}
