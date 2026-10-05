import ts from 'typescript';

type MembersNode = ts.InterfaceDeclaration | ts.TypeLiteralNode;

export function memberName(member: ts.TypeElement): string {
  if (!member.name || (!ts.isIdentifier(member.name) && !ts.isStringLiteral(member.name))) {
    throw new Error('Unsupported OpenAPI declaration member');
  }
  return member.name.text;
}

export function withMembers<T extends MembersNode>(node: T, members: ts.TypeElement[]): T {
  return (ts.isInterfaceDeclaration(node)
    ? ts.factory.updateInterfaceDeclaration(node, node.modifiers, node.name, node.typeParameters, node.heritageClauses, members)
    : ts.factory.updateTypeLiteralNode(node, ts.factory.createNodeArray(members))) as T;
}

export function schemaMembers(components: ts.InterfaceDeclaration): readonly ts.TypeElement[] {
  const schemas = components.members.find((member) => memberName(member) === 'schemas') as ts.PropertySignature | undefined;
  return schemas?.type && ts.isTypeLiteralNode(schemas.type) ? schemas.type.members : [];
}

export function componentNode(original: ts.InterfaceDeclaration, schemas: ts.TypeElement[]): ts.InterfaceDeclaration {
  return withMembers(original, original.members.map((member) => {
    if (memberName(member) !== 'schemas') return member;
    const property = member as ts.PropertySignature;
    return ts.factory.updatePropertySignature(property, property.modifiers, property.name, property.questionToken, ts.factory.createTypeLiteralNode(schemas));
  }));
}

export function declaration(ast: ts.Node[], name: string): ts.InterfaceDeclaration {
  const node = ast.find((node) => (ts.isInterfaceDeclaration(node) || ts.isTypeAliasDeclaration(node)) && node.name.text === name);
  if (!node) throw new Error(`Missing OpenAPI declaration ${name}`);
  if (ts.isInterfaceDeclaration(node)) return node;
  // openapi-typescript emits never/Record<string, never> aliases for empty sections.
  return ts.factory.createInterfaceDeclaration([ts.factory.createModifier(ts.SyntaxKind.ExportKeyword)], name, undefined, undefined, []);
}
