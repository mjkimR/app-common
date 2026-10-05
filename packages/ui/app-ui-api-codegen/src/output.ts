import fs from 'node:fs';
import path from 'node:path';
import { generatedHeader } from './generate.js';

/** Update only owned declarations; check mode never mutates the output directory. */
export function writeContract(files: ReadonlyMap<string, string>, outputDir: string, options: { check?: boolean } = {}): void {
  const existing = fs.existsSync(outputDir) ? fs.readdirSync(outputDir) : [];
  const owned = new Set<string>();
  for (const name of existing) {
    const file = path.join(outputDir, name);
    const stat = fs.lstatSync(file);
    if (stat.isFile() && name.endsWith('.d.ts') && fs.readFileSync(file, 'utf8').startsWith(generatedHeader.trimEnd())) owned.add(name);
  }
  for (const [name, content] of files) {
    if (!/^[a-z][a-z0-9-]*\.d\.ts$/.test(name) || !content.startsWith(generatedHeader)) throw new Error(`Invalid generated declaration ${name}`);
    if (existing.includes(name) && !owned.has(name)) throw new Error(`Refusing to overwrite unowned file ${name}`);
  }
  const stale = [...owned].filter((name) => !files.has(name));
  const changed = [...files].filter(([name, content]) => !owned.has(name) || fs.readFileSync(path.join(outputDir, name), 'utf8').replace(/\r\n/g, '\n') !== content).map(([name]) => name);
  if (options.check) {
    if (changed.length || stale.length) throw new Error(`API contract is out of date (${[...changed, ...stale].join(', ')}). Run the project's API generation command.`);
    return;
  }
  fs.mkdirSync(outputDir, { recursive: true });
  for (const name of changed) fs.writeFileSync(path.join(outputDir, name), files.get(name)!, 'utf8');
  for (const name of stale) fs.unlinkSync(path.join(outputDir, name));
}
