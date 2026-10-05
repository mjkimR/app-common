import openapiTS, { astToString, type OpenAPI3 } from 'openapi-typescript';
import ts from 'typescript';
import { componentNode, declaration, memberName, schemaMembers, withMembers } from './ast.js';
import { partition } from './domains.js';

export const generatedHeader = '/** Generated from OpenAPI domain tags. Do not edit manually. */\n';

/** Generate declarations without writing files or fetching a backend schema. */
export async function generateContract(document: OpenAPI3): Promise<Map<string, string>> {
  const { domains, shared } = partition(document);
  const ast = await openapiTS(document, { defaultNonNullable: false });
  const components = declaration(ast, 'components');
  const paths = declaration(ast, 'paths');
  const operations = declaration(ast, 'operations');
  const schemas = schemaMembers(components);
  const sorted = [...domains].sort(([a], [b]) => a.localeCompare(b));
  const files = new Map<string, string>();
  files.set('common.d.ts', generatedHeader + astToString([
    componentNode(components, schemas.filter((member) => shared.has(memberName(member))))
  ]));
  for (const [tag, domain] of sorted) {
    const members = schemas.filter((member) => domain.schemas.has(memberName(member))).map((member) => {
      if (!shared.has(memberName(member))) return member;
      const reference = ts.factory.createIndexedAccessTypeNode(
        ts.factory.createIndexedAccessTypeNode(ts.factory.createTypeReferenceNode('CommonComponents'), ts.factory.createLiteralTypeNode(ts.factory.createStringLiteral('schemas'))),
        ts.factory.createLiteralTypeNode(ts.factory.createStringLiteral(memberName(member)))
      );
      return ts.factory.createPropertySignature(undefined, member.name!, undefined, reference);
    });
    const nodes = [
      withMembers(paths, paths.members.filter((member) => domain.routes.has(memberName(member)))),
      componentNode(components, members),
      withMembers(operations, operations.members.filter((member) => domain.operations.has(memberName(member))))
    ];
    files.set(`${tag}.d.ts`, generatedHeader + 'import type { components as CommonComponents } from "./common";\n' + astToString(nodes));
  }
  const imports = sorted.map(([tag], i) => `import type { paths as Paths${i}, components as Components${i} } from './${tag}';`);
  files.set('index.d.ts', generatedHeader + [
    "import type { components as CommonComponents } from './common';",
    ...imports,
    `export type paths = ${sorted.map((_, i) => `Paths${i}`).join(' & ') || 'Record<string, never>'};`,
    `export type components = CommonComponents${sorted.map((_, i) => ` & Components${i}`).join('')};`,
    ''
  ].join('\n'));
  return files;
}
