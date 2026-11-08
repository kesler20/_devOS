import * as types from "./relational.types";
import type { RelationalConstraint } from "./relationalEditing";

export type StudioMode = "schema" | "orm";
export type StudioFileAction = "new" | "open" | "export-json" | "export-sql" | "namespaces" | "enums";
export type EditorDraft =
  | { kind: "table"; table: types.Table; ormAlias: string; color: string }
  | { kind: "column"; tableId: string; column: types.Column; ormAlias: string }
  | { kind: "constraint"; tableId: string; constraint: RelationalConstraint; ormAlias: string; reverseAlias: string; cascade: types.OrmRelationship["cascade"] }
  | { kind: "index"; tableId: string; index: types.Index }
  | { kind: "namespace"; namespace: types.Namespace }
  | { kind: "enum"; enum: types.EnumType }
  | { kind: "catalog"; catalog: "namespaces" | "enums" };

export type EditorField = "name" | "quoted" | "namespace_id" | "description" | "orm_alias" | "reverse_alias" | "color" | "type" | "length" | "precision" | "scale" | "time_precision" | "enum_id" | "array_dimensions" | "nullable" | "default" | "generation" | "start" | "increment" | "min_value" | "max_value" | "cache" | "cycle" | "expression" | "target_table_id" | "on_delete" | "on_update" | "match" | "deferrable" | "initially_deferred" | "cascade" | "unique";
