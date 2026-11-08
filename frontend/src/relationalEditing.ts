import * as types from "./relational.types";
import { renameCheckColumn } from "./relationalExpressions";
import { validateRelational } from "./validateRelational";

export type RelationalConstraint = types.KeyConstraint | types.ForeignKey | types.CheckConstraint;

export function ormClassName(document: types.SchemaDocument, table: types.Table): string {
  const alias = document.orm?.tables?.find(item => item.table_id === table.id)?.class_name;
  if (alias) return alias;
  return table.name.name.split(/[^a-zA-Z0-9]+/).filter(Boolean).map(word => word[0].toUpperCase() + word.slice(1)).join("") + "DAO";
}

export function ormAttributeName(document: types.SchemaDocument, column: types.Column): string {
  return document.orm?.columns?.find(item => item.column_id === column.id)?.attribute_name ?? column.name.name;
}

export function navigationNames(document: types.SchemaDocument, table: types.Table, key: types.ForeignKey): { attribute_name: string; reverse_attribute_name: string } {
  const target = document.tables?.find(item => item.id === key.target_table_id);
  if (!target) throw new Error("Foreign-key target no longer exists");
  const path = key.column_ids.map(id => ormAttributeName(document, table.columns.find(column => column.id === id)!)).join("_");
  const configuration = document.orm?.relationships?.find(item => item.foreign_key_id === key.id);
  return {
    attribute_name: configuration?.attribute_name ?? ormClassName(document, target).replace(/DAO$/, "").toLowerCase() + "_via_" + path,
    reverse_attribute_name: configuration?.reverse_attribute_name ?? "referenced_by_" + ormClassName(document, table).replace(/DAO$/, "").toLowerCase() + "_via_" + path,
  };
}

export function tableAlias(document: types.SchemaDocument, tableId: string, alias: string): types.SchemaDocument {
  const tables = (document.orm?.tables ?? []).filter(item => item.table_id !== tableId);
  if (alias) tables.push({ table_id: tableId, class_name: alias });
  return validateRelational({ ...document, orm: { ...document.orm, tables } });
}

export function columnAlias(document: types.SchemaDocument, columnId: string, alias: string): types.SchemaDocument {
  const columns = (document.orm?.columns ?? []).filter(item => item.column_id !== columnId);
  if (alias) columns.push({ column_id: columnId, attribute_name: alias });
  return validateRelational({ ...document, orm: { ...document.orm, columns } });
}

export function relationshipConfiguration(document: types.SchemaDocument, configuration: types.OrmRelationship): types.SchemaDocument {
  const relationships = (document.orm?.relationships ?? []).filter(item => item.foreign_key_id !== configuration.foreign_key_id);
  relationships.push(configuration);
  return validateRelational({ ...document, orm: { ...document.orm, relationships } });
}

export function createDocument(): types.SchemaDocument {
  return { version: 1, namespaces: [{ id: crypto.randomUUID(), name: { name: "public" } }], enums: [], tables: [] };
}

export function replaceTable(document: types.SchemaDocument, table: types.Table): types.SchemaDocument {
  const exists = (document.tables ?? []).some(item => item.id === table.id);
  const tables = exists ? (document.tables ?? []).map(item => item.id === table.id ? table : item) : [...(document.tables ?? []), table];
  return validateRelational({ ...document, tables });
}

export function replaceColumn(document: types.SchemaDocument, tableId: string, column: types.Column): types.SchemaDocument {
  const table = (document.tables ?? []).find(item => item.id === tableId);
  if (!table) throw new Error("Selected table no longer exists");
  const existing = table.columns.find(item => item.id === column.id);
  const renamed = existing && existing.name.name !== column.name.name ? renameCheckColumn(table, existing.name.name, column.name.name) : table;
  const columns = existing ? renamed.columns.map(item => item.id === column.id ? column : item) : [...renamed.columns, column];
  return replaceTable(document, { ...renamed, columns });
}

export function deleteColumn(document: types.SchemaDocument, tableId: string, columnId: string): types.SchemaDocument {
  const table = (document.tables ?? []).find(item => item.id === tableId);
  if (!table) throw new Error("Selected table no longer exists");
  const candidate = { ...document, orm: document.orm ? { ...document.orm, columns: (document.orm.columns ?? []).filter(item => item.column_id !== columnId) } : document.orm };
  return replaceTable(candidate, { ...table, columns: table.columns.filter(item => item.id !== columnId) });
}

export function deleteTable(document: types.SchemaDocument, tableId: string): types.SchemaDocument {
  const table = (document.tables ?? []).find(item => item.id === tableId);
  if (!table) throw new Error("Selected table no longer exists");
  const columnIds = new Set(table.columns.map(column => column.id));
  const foreignKeyIds = new Set((table.constraints ?? []).filter(item => item.kind === "foreign_key").map(item => item.id));
  return validateRelational({
    ...document,
    tables: (document.tables ?? []).filter(item => item.id !== tableId),
    diagram: document.diagram ? { ...document.diagram, tables: (document.diagram.tables ?? []).filter(item => item.table_id !== tableId) } : document.diagram,
    orm: document.orm ? {
      ...document.orm,
      tables: (document.orm.tables ?? []).filter(item => item.table_id !== tableId),
      columns: (document.orm.columns ?? []).filter(item => !columnIds.has(item.column_id)),
      relationships: (document.orm.relationships ?? []).filter(item => !foreignKeyIds.has(item.foreign_key_id)),
    } : document.orm,
  });
}

export function replaceConstraint(document: types.SchemaDocument, tableId: string, constraint: RelationalConstraint): types.SchemaDocument {
  const table = (document.tables ?? []).find(item => item.id === tableId);
  if (!table) throw new Error("Selected table no longer exists");
  const constraints = table.constraints ?? [];
  const exists = constraints.some(item => item.id === constraint.id);
  return replaceTable(document, { ...table, constraints: exists ? constraints.map(item => item.id === constraint.id ? constraint : item) : [...constraints, constraint] });
}

export function deleteConstraint(document: types.SchemaDocument, tableId: string, constraintId: string): types.SchemaDocument {
  const table = (document.tables ?? []).find(item => item.id === tableId);
  if (!table) throw new Error("Selected table no longer exists");
  return replaceTable({ ...document, orm: document.orm ? { ...document.orm, relationships: (document.orm.relationships ?? []).filter(item => item.foreign_key_id !== constraintId) } : document.orm }, { ...table, constraints: (table.constraints ?? []).filter(item => item.id !== constraintId) });
}

export function replaceIndex(document: types.SchemaDocument, tableId: string, index: types.Index): types.SchemaDocument {
  const table = (document.tables ?? []).find(item => item.id === tableId);
  if (!table) throw new Error("Selected table no longer exists");
  const indexes = table.indexes ?? [];
  return replaceTable(document, { ...table, indexes: indexes.some(item => item.id === index.id) ? indexes.map(item => item.id === index.id ? index : item) : [...indexes, index] });
}

export function deleteIndex(document: types.SchemaDocument, tableId: string, indexId: string): types.SchemaDocument {
  const table = (document.tables ?? []).find(item => item.id === tableId);
  if (!table) throw new Error("Selected table no longer exists");
  return replaceTable(document, { ...table, indexes: (table.indexes ?? []).filter(item => item.id !== indexId) });
}

export function reorderColumns(document: types.SchemaDocument, tableId: string, columnIds: string[]): types.SchemaDocument {
  const table = (document.tables ?? []).find(item => item.id === tableId);
  if (!table || columnIds.length !== table.columns.length || new Set(columnIds).size !== columnIds.length) throw new Error("Column order must contain every owned column exactly once");
  const columns = columnIds.map(id => {
    const column = table.columns.find(item => item.id === id);
    if (!column) throw new Error("Column order contains an unknown column");
    return column;
  });
  return replaceTable(document, { ...table, columns });
}

export function exportDocument(document: types.SchemaDocument): string {
  const validated = validateRelational(document);
  const tables = (validated.tables ?? []).map(table => ({
    ...table,
    columns: table.columns.map(column => {
      const identity = column.identity;
      if (!identity) return column;
      return { ...column, identity: {
        ...identity,
        start: identity.start == null ? identity.start : String(identity.start),
        increment: identity.increment == null ? identity.increment : String(identity.increment),
        min_value: identity.min_value == null ? identity.min_value : String(identity.min_value),
        max_value: identity.max_value == null ? identity.max_value : String(identity.max_value),
        cache: identity.cache == null ? identity.cache : String(identity.cache),
      } };
    }),
  }));
  return JSON.stringify({ ...validated, tables }, null, 2) + "\n";
}

export function openDocument(source: string): types.SchemaDocument {
  return validateRelational(JSON.parse(source));
}
