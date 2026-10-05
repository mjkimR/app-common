import type { OpenAPI3, OperationObject, SchemaObject } from 'openapi-typescript';

const methods = new Set(['get', 'put', 'post', 'delete', 'options', 'head', 'patch', 'trace']);

export interface Domain {
  routes: Set<string>;
  operations: Set<string>;
  roots: Set<string>;
  schemas: Set<string>;
}

function references(value: unknown, found = new Set<string>()): Set<string> {
  if (!value || typeof value !== 'object') return found;
  if ('$ref' in value && typeof value.$ref === 'string') {
    if (!value.$ref.startsWith('#/components/schemas/')) {
      throw new Error(`Unsupported reference ${value.$ref}: use local schema references.`);
    }
    found.add(value.$ref.slice('#/components/schemas/'.length).replace(/~1/g, '/').replace(/~0/g, '~'));
  }
  for (const child of Object.values(value)) references(child, found);
  return found;
}

function closure(roots: Iterable<string>, schemas: Record<string, SchemaObject>): Set<string> {
  const found = new Set(roots);
  for (const name of found) {
    if (!Object.hasOwn(schemas, name)) throw new Error(`Missing schema ${name}`);
    for (const dependency of references(schemas[name])) found.add(dependency);
  }
  return found;
}

export function partition(document: OpenAPI3): { domains: Map<string, Domain>; shared: Set<string> } {
  // Webhooks and $defs cannot be represented by this paths/components contract.
  if (Object.keys(document.webhooks ?? {}).length || Object.keys(document.$defs ?? {}).length) {
    throw new Error('Webhooks and $defs are not supported by the domain contract.');
  }
  const domains = new Map<string, Domain>();
  const operationIds = new Set<string>();
  for (const [route, item] of Object.entries(document.paths ?? {}).sort()) {
    if ('$ref' in item) throw new Error(`Unsupported path reference at ${route}`);
    const tags = new Set<string>();
    const ids: string[] = [];
    for (const [method, value] of Object.entries(item)) {
      if (!methods.has(method)) continue;
      const operation = value as OperationObject;
      const [tag] = operation.tags ?? [];
      if (
        operation.tags?.length !== 1 || !tag || !/^[a-z][a-z0-9-]*$/.test(tag) ||
        ['common', 'index'].includes(tag) || /^(con|prn|aux|nul|com[0-9]|lpt[0-9])$/.test(tag)
      ) {
        throw new Error(`${method.toUpperCase()} ${route}: declare exactly one domain tag (lowercase kebab case; common/index and Windows device names are reserved).`);
      }
      if (!operation.operationId) throw new Error(`${method.toUpperCase()} ${route}: missing operationId`);
      if (operationIds.has(operation.operationId)) throw new Error(`Duplicate operationId ${operation.operationId}`);
      operationIds.add(operation.operationId);
      tags.add(tag);
      ids.push(operation.operationId);
    }
    if (!tags.size) continue;
    if (tags.size !== 1) throw new Error(`${route}: all methods on a path must share one domain tag.`);
    const tag = [...tags][0];
    let domain = domains.get(tag);
    if (!domain) {
      domain = { routes: new Set(), operations: new Set(), roots: new Set(), schemas: new Set() };
      domains.set(tag, domain);
    }
    domain.routes.add(route);
    for (const id of ids) domain.operations.add(id);
    references(item, domain.roots);
  }

  const schemas = document.components?.schemas ?? {};
  const componentRoots = references(Object.fromEntries(Object.entries(document.components ?? {}).filter(([name]) => name !== 'schemas')));
  const consumers = new Map(Object.keys(schemas).map((name) => [name, new Set<string>()]));
  for (const [tag, domain] of domains) {
    for (const name of componentRoots) domain.roots.add(name);
    domain.schemas = closure(domain.roots, schemas);
    for (const name of domain.schemas) consumers.get(name)!.add(tag);
  }
  // Unused schemas remain available through the aggregate components type.
  const shared = closure([...componentRoots, ...[...consumers].filter(([, tags]) => tags.size !== 1).map(([name]) => name)], schemas);
  return { domains, shared };
}
