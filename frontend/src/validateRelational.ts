import Ajv from "ajv";
import * as types from "./relational.types";
import { validateSqlExpressions } from "./relationalExpressions";

const schema = require("./relational.schema.json");
const validator = new Ajv({ strict: false, allErrors: true }).compile(schema);

export function validateRelational(value: unknown): types.SchemaDocument {
  if (!validator(value)) {
    throw new Error(validator.errors?.map(error => `${error.instancePath} ${error.message}`).join("\n"));
  }
  const document = value as types.SchemaDocument;
  const namespaces = document.namespaces ?? [];
  const enums = document.enums ?? [];
  const tables = document.tables ?? [];
  const objects = [
    ...namespaces, ...enums, ...tables,
    ...tables.flatMap(table => [...table.columns, ...(table.constraints ?? []), ...(table.indexes ?? [])]),
  ];
  const ids = objects.map(item => item.id);
  if (new Set(ids).size !== ids.length) throw new Error("Duplicate stable ID in document");
  if (new Set(namespaces.map(item => item.name.name)).size !== namespaces.length) throw new Error("Duplicate namespace name");
  const namespaceIds = new Set(namespaces.map(item => item.id));
  const tableIds = new Set(tables.map(item => item.id));
  const enumIds = new Set(enums.map(item => item.id));
  const qualifiedNames = [...enums, ...tables].map(item => JSON.stringify([item.namespace_id, item.name.name]));
  if (new Set(qualifiedNames).size !== qualifiedNames.length) throw new Error("Duplicate table/enum SQL name in namespace");
  for (const item of [...tables, ...enums]) {
    if (!namespaceIds.has(item.namespace_id)) throw new Error(`${item.id} references missing namespace`);
  }
  const identifiers = [
    ...namespaces.map(item => item.name), ...enums.map(item => item.name), ...tables.map(item => item.name),
    ...tables.flatMap(table => table.columns.map(item => item.name)),
    ...tables.flatMap(table => (table.constraints ?? []).flatMap(item => item.name ? [item.name] : [])),
    ...tables.flatMap(table => (table.indexes ?? []).map(item => item.name)),
  ];
  const utf8Length = (text: string) => encodeURIComponent(text).replace(/%[A-F\d]{2}|./g, "x").length;
  for (const identifier of identifiers) {
    if (identifier.name.includes("\0") || utf8Length(identifier.name) > 63) throw new Error("SQL identifiers must fit 63 UTF-8 bytes and contain no NUL");
    if (!identifier.quoted && !/^[a-z_][a-z0-9_$]*$/.test(identifier.name)) throw new Error("Unquoted identifiers must be lowercase SQL names");
  }
  for (const item of enums) {
    if (new Set(item.values).size !== item.values.length) throw new Error("Enum labels must be unique");
    if (item.values.some(value => value.includes("\0") || utf8Length(value) > 63)) throw new Error("Enum labels must fit 63 UTF-8 bytes and contain no NUL");
  }
  const indexNames = new Set<string>();
  for (const table of tables) {
    validateSqlExpressions(table);
    const columnIds = new Set(table.columns.map(column => column.id));
    if (new Set(table.columns.map(column => column.name.name)).size !== table.columns.length) throw new Error(`Duplicate column name in ${table.id}`);
    const constraintNames = (table.constraints ?? []).flatMap(item => item.name ? [item.name.name] : []);
    if (new Set(constraintNames).size !== constraintNames.length) throw new Error(`Duplicate constraint name in ${table.id}`);
    const primaryKeys = (table.constraints ?? []).filter(item => item.kind === "primary_key");
    if (primaryKeys.length > 1) throw new Error(`Multiple primary keys in ${table.id}`);
    for (const column of table.columns) {
      const type = column.type;
      if (type.length != null && !["varchar", "char"].includes(type.name)) throw new Error("length applies only to varchar/char");
      if ((type.precision != null || type.scale != null) && type.name !== "numeric") throw new Error("precision/scale apply only to numeric");
      if (type.scale != null && type.precision == null) throw new Error("numeric scale requires precision");
      if (type.time_precision != null && !["time", "timetz", "timestamp", "timestamptz", "interval"].includes(type.name)) throw new Error("time_precision applies only to temporal types");
      if ((type.name === "enum") !== (type.enum_id != null)) throw new Error("enum types require enum_id, other types must omit it");
      if (type.enum_id != null && !enumIds.has(type.enum_id)) throw new Error(`${column.id} references missing enum`);
      if (column.serial || column.identity != null) {
        if (!["smallint", "integer", "bigint"].includes(type.name) || type.array_dimensions) throw new Error("Serial/identity requires a scalar integer type");
        if ((column.serial && column.identity != null) || column.default != null) throw new Error("Serial, identity and explicit defaults are mutually exclusive");
        if (column.nullable ?? true) throw new Error("Serial/identity columns must be non-nullable");
      }
      const identity = column.identity;
      if (identity) {
        const value = (input: number | string | null | undefined): bigint | undefined => {
          if (input == null) return undefined;
          if (typeof input === "number" && !Number.isSafeInteger(input)) throw new Error("Identity integers outside the JavaScript safe range must be decimal strings");
          if (typeof input === "string" && !/^(?:0|[1-9][0-9]*|-[1-9][0-9]*)$/.test(input)) throw new Error("Identity options require canonical decimal strings");
          const parsed = BigInt(input);
          if (parsed < -9223372036854775808n || parsed > 9223372036854775807n) throw new Error("Identity options must fit signed 64-bit integers");
          return parsed;
        };
        const start = value(identity.start);
        const increment = value(identity.increment);
        const minimum = value(identity.min_value);
        const maximum = value(identity.max_value);
        const cache = value(identity.cache);
        if (increment === 0n) throw new Error("Identity increment must not be zero");
        if (cache != null && cache < 1n) throw new Error("Identity cache must be at least one");
        if (minimum != null && maximum != null && minimum >= maximum) throw new Error("Identity minimum must be below maximum");
        if (start != null && minimum != null && start < minimum) throw new Error("Identity start must be at least minimum");
        if (start != null && maximum != null && start > maximum) throw new Error("Identity start must be at most maximum");
      }
    }
    for (const constraint of [...(table.constraints ?? []), ...(table.indexes ?? [])]) {
      if ("kind" in constraint && constraint.kind === "check") continue;
      const key = constraint as types.KeyConstraint | types.ForeignKey | types.Index;
      if (new Set(key.column_ids).size !== key.column_ids.length) throw new Error(`${key.id} repeats a key column`);
      if (key.column_ids.some(id => !columnIds.has(id))) throw new Error(`${key.id} references columns outside ${table.id}`);
      if (!("kind" in key)) {
        const qualifiedName = JSON.stringify([table.namespace_id, key.name.name]);
        if (indexNames.has(qualifiedName) || qualifiedNames.includes(qualifiedName)) throw new Error(`Duplicate index/relation name for ${key.id}`);
        indexNames.add(qualifiedName);
        continue;
      }
      if (key.initially_deferred && !key.deferrable) throw new Error(`${key.id} initially_deferred requires deferrable`);
      if (key.kind === "primary_key" && key.column_ids.some(id => table.columns.find(column => column.id === id)?.nullable ?? true)) throw new Error(`${key.id} primary key columns must be non-nullable`);
      if (key.kind !== "foreign_key") continue;
      const target = tables.find(table => table.id === key.target_table_id);
      if (!target) throw new Error(`${key.id} references missing target table`);
      if (key.target_column_ids.some(id => !target.columns.some(column => column.id === id))) throw new Error(`${key.id} references columns outside target table`);
      if (key.column_ids.length !== key.target_column_ids.length) throw new Error(`${key.id} foreign key pairs must have equal lengths`);
      if (new Set(key.target_column_ids).size !== key.target_column_ids.length) throw new Error(`${key.id} repeats a target column`);
      const candidates = [
        ...(target.constraints ?? []).filter(item => ["primary_key", "unique"].includes(item.kind) && !(item as types.KeyConstraint).deferrable),
        ...(target.indexes ?? []).filter(item => item.unique),
      ] as Array<types.KeyConstraint | types.Index>;
      if (!candidates.some(candidate => candidate.column_ids.length === key.target_column_ids.length && candidate.column_ids.every(id => key.target_column_ids.includes(id)))) throw new Error(`${key.id} target is not a non-deferrable unique key`);
    }
  }
  const layoutIds = (document.diagram?.tables ?? []).map(item => item.table_id);
  if (new Set(layoutIds).size !== layoutIds.length || layoutIds.some(id => !tableIds.has(id))) throw new Error("Diagram contains duplicate or missing table references");
  const positions = document.diagram?.tables ?? [];
  if (positions.some(item => !Number.isFinite(item.x) || !Number.isFinite(item.y))) throw new Error("Diagram coordinates must be finite");
  if (document.diagram?.viewport && Object.values(document.diagram.viewport).some(value => !Number.isFinite(value))) throw new Error("Viewport coordinates must be finite");
  const orm = document.orm;
  if (orm) {
    const columnIds = new Set(tables.flatMap(table => table.columns.map(column => column.id)));
    const foreignKeyIds = new Set(tables.flatMap(table => (table.constraints ?? []).filter(item => item.kind === "foreign_key").map(item => item.id)));
    const aliases: Array<{ ids: string[]; available: Set<string>; field: string }> = [
      { ids: (orm.tables ?? []).map(item => item.table_id), available: tableIds, field: "table_id" },
      { ids: (orm.columns ?? []).map(item => item.column_id), available: columnIds, field: "column_id" },
      { ids: (orm.relationships ?? []).map(item => item.foreign_key_id), available: foreignKeyIds, field: "foreign_key_id" },
    ];
    for (const group of aliases) {
      if (new Set(group.ids).size !== group.ids.length || group.ids.some(id => !group.available.has(id))) throw new Error(`ORM configuration has duplicate/missing ${group.field}`);
    }
    const names = [
      ...(orm.tables ?? []).map(item => item.class_name), ...(orm.columns ?? []).map(item => item.attribute_name),
      ...(orm.relationships ?? []).flatMap(item => [item.attribute_name, ...(item.reverse_attribute_name ? [item.reverse_attribute_name] : [])]),
    ];
    const keywords = new Set("False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield".split(" "));
    if (names.some(name => !/^[_\p{L}][\p{L}\p{N}_]*$/u.test(name) || keywords.has(name))) throw new Error("ORM aliases must be Python identifiers");
    if ((orm.tables ?? []).some(item => ["Base", "sa", "orm", "pg"].includes(item.class_name) || /^(enum_|table_)/.test(item.class_name))) throw new Error("ORM class_name alias must be non-reserved");
    if ((orm.columns ?? []).some(item => ["metadata", "registry"].includes(item.attribute_name) || item.attribute_name.startsWith("__"))) throw new Error("ORM attribute_name alias must be non-reserved");
    if ((orm.relationships ?? []).flatMap(item => [item.attribute_name, ...(item.reverse_attribute_name ? [item.reverse_attribute_name] : [])]).some(name => ["metadata", "registry"].includes(name) || name.startsWith("__"))) throw new Error("ORM relationship aliases must be non-reserved");
    if (new Set((orm.tables ?? []).map(item => item.class_name)).size !== (orm.tables ?? []).length) throw new Error("ORM class names must be unique");
  }
  return document;
}
