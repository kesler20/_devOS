// Generated from devOS.domain.relational.SchemaDocument.

export type CheckConstraint = {
  "id": string;
  "kind": "check";
  "name"?: (SqlIdentifier | null);
  "expression": string;
};

export type Column = {
  "id": string;
  "name": SqlIdentifier;
  "type": SqlType;
  "nullable"?: boolean;
  "description"?: (string | null);
  "default"?: (string | null);
  "serial"?: boolean;
  "identity"?: (Identity | null);
};

export type DiagramLayout = {
  "tables"?: Array<TablePosition>;
  "viewport"?: (Viewport | null);
};

export type EnumType = {
  "id": string;
  "namespace_id": string;
  "name": SqlIdentifier;
  "values": Array<string>;
  "description"?: (string | null);
};

export type ForeignKey = {
  "id": string;
  "kind": "foreign_key";
  "name"?: (SqlIdentifier | null);
  "column_ids": Array<string>;
  "target_table_id": string;
  "target_column_ids": Array<string>;
  "on_delete"?: "NO ACTION" | "RESTRICT" | "CASCADE" | "SET NULL" | "SET DEFAULT";
  "on_update"?: "NO ACTION" | "RESTRICT" | "CASCADE" | "SET NULL" | "SET DEFAULT";
  "match"?: "SIMPLE" | "FULL";
  "deferrable"?: boolean;
  "initially_deferred"?: boolean;
};

export type Identity = {
  "generation"?: "always" | "by_default";
  "start"?: ((number | string) | null);
  "increment"?: ((number | string) | null);
  "min_value"?: ((number | string) | null);
  "max_value"?: ((number | string) | null);
  "cache"?: ((number | string) | null);
  "cycle"?: boolean;
};

export type Index = {
  "id": string;
  "name": SqlIdentifier;
  "column_ids": Array<string>;
  "unique"?: boolean;
  "method"?: "btree";
};

export type KeyConstraint = {
  "id": string;
  "kind": "primary_key" | "unique";
  "name"?: (SqlIdentifier | null);
  "column_ids": Array<string>;
  "deferrable"?: boolean;
  "initially_deferred"?: boolean;
};

export type Namespace = {
  "id": string;
  "name": SqlIdentifier;
  "description"?: (string | null);
};

export type OrmColumn = {
  "column_id": string;
  "attribute_name": string;
};

export type OrmConfiguration = {
  "tables"?: Array<OrmTable>;
  "columns"?: Array<OrmColumn>;
  "relationships"?: Array<OrmRelationship>;
};

export type OrmRelationship = {
  "foreign_key_id": string;
  "attribute_name": string;
  "reverse_attribute_name"?: (string | null);
  "cascade"?: "save-update, merge" | "all" | "all, delete-orphan";
};

export type OrmTable = {
  "table_id": string;
  "class_name": string;
};

export type SqlIdentifier = {
  "name": string;
  "quoted"?: boolean;
};

export type SqlType = {
  "name": "smallint" | "integer" | "bigint" | "numeric" | "real" | "double precision" | "boolean" | "text" | "varchar" | "char" | "uuid" | "date" | "time" | "timetz" | "timestamp" | "timestamptz" | "interval" | "bytea" | "json" | "jsonb" | "enum";
  "length"?: (number | null);
  "precision"?: (number | null);
  "scale"?: (number | null);
  "time_precision"?: (number | null);
  "enum_id"?: (string | null);
  "array_dimensions"?: number;
};

export type Table = {
  "id": string;
  "namespace_id": string;
  "name": SqlIdentifier;
  "description"?: (string | null);
  "columns": Array<Column>;
  "constraints"?: Array<(KeyConstraint | ForeignKey | CheckConstraint)>;
  "indexes"?: Array<Index>;
};

export type TablePosition = {
  "table_id": string;
  "x": number;
  "y": number;
  "color"?: (string | null);
};

export type Viewport = {
  "x"?: number;
  "y"?: number;
  "zoom"?: number;
};

export type SchemaDocument = {
  "version"?: 1;
  "namespaces"?: Array<Namespace>;
  "enums"?: Array<EnumType>;
  "tables"?: Array<Table>;
  "diagram"?: (DiagramLayout | null);
  "orm"?: (OrmConfiguration | null);
};

export const sqlTypeNames: Array<SqlType["name"]> = ["smallint", "integer", "bigint", "numeric", "real", "double precision", "boolean", "text", "varchar", "char", "uuid", "date", "time", "timetz", "timestamp", "timestamptz", "interval", "bytea", "json", "jsonb", "enum"];
