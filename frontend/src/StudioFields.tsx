import * as types from "./relational.types";
import * as editing from "./relationalEditing";

// ============================================================ //
//                                                              //
//   TABLE FIELDS / COLUMN FIELDS / CONSTRAINT FIELDS           //
//   ORDERED COLUMNS / INDEX FIELDS / NAMESPACE FIELDS          //
//   ENUM FIELDS                                                //
//                                                              //
//   Stateless authoring fields shared by Studio editor layouts. //
//   Drafts and validation belong to the page. Controls emit     //
//   field values and ordered-column events upward.             //
//                                                              //
// ============================================================ //

export type TableInputField = "name" | "quoted" | "namespace_id" | "description" | "orm_alias" | "color";
export type ColumnInputField = "name" | "quoted" | "description" | "type" | "length" | "precision" | "scale" | "time_precision" | "enum_id" | "array_dimensions" | "nullable" | "default" | "generation" | "start" | "increment" | "min_value" | "max_value" | "cache" | "cycle" | "orm_alias";
export type ConstraintInputField = "name" | "quoted" | "expression" | "target_table_id" | "on_delete" | "on_update" | "match" | "deferrable" | "initially_deferred" | "orm_alias" | "reverse_alias" | "cascade";

const typeNames = types.sqlTypeNames;
const actions: Array<NonNullable<types.ForeignKey["on_delete"]>> = ["NO ACTION", "RESTRICT", "CASCADE", "SET NULL", "SET DEFAULT"];



export function TableFields(props: {
  table: types.Table;
  namespaces: types.Namespace[];
  ormAlias: string;
  color: string;
  ormMode: boolean;
  onEventField: (field: TableInputField, value: string | boolean) => void;
}) {
  if (props.ormMode) return <label>ORM class alias<input value={props.ormAlias} onChange={event => props.onEventField("orm_alias", event.target.value)} /></label>;
  return <>
    <label>Namespace<select value={props.table.namespace_id} onChange={event => props.onEventField("namespace_id", event.target.value)}>{props.namespaces.map(item => <option key={item.id} value={item.id}>{item.name.name}</option>)}</select></label>
    <label>Name<input value={props.table.name.name} onChange={event => props.onEventField("name", event.target.value)} /></label>
    <label className="studio-checkbox"><input type="checkbox" checked={props.table.name.quoted ?? false} onChange={event => props.onEventField("quoted", event.target.checked)} />Quoted name</label>
    <label>Description<textarea value={props.table.description ?? ""} onChange={event => props.onEventField("description", event.target.value)} /></label>
    <label>Colour<input type="color" value={props.color} onChange={event => props.onEventField("color", event.target.value)} /></label>
  </>;
}

export function ColumnFields(props: {
  column: types.Column;
  enums: types.EnumType[];
  ormAlias: string;
  ormMode: boolean;
  onEventField: (field: ColumnInputField, value: string | boolean) => void;
}) {
  if (props.ormMode) return <label>ORM attribute alias<input value={props.ormAlias} onChange={event => props.onEventField("orm_alias", event.target.value)} /></label>;
  const generation = props.column.serial ? "serial" : props.column.identity?.generation ?? (props.column.identity ? "by_default" : "none");
  return <>
    {/* Column identity */}
    <label>Name<input value={props.column.name.name} onChange={event => props.onEventField("name", event.target.value)} /></label>
    <label className="studio-checkbox"><input type="checkbox" checked={props.column.name.quoted ?? false} onChange={event => props.onEventField("quoted", event.target.checked)} />Quoted name</label>
    {/* SQL type and parameters */}
    <label>Type<select value={props.column.type.name} onChange={event => props.onEventField("type", event.target.value)}>{typeNames.map(name => <option key={name}>{name}</option>)}</select></label>
    {["varchar", "char"].includes(props.column.type.name) && <label>Length<input type="number" value={props.column.type.length ?? ""} onChange={event => props.onEventField("length", event.target.value)} /></label>}
    {props.column.type.name === "numeric" && <>
      <label>Precision<input type="number" value={props.column.type.precision ?? ""} onChange={event => props.onEventField("precision", event.target.value)} /></label>
      <label>Scale<input type="number" value={props.column.type.scale ?? ""} onChange={event => props.onEventField("scale", event.target.value)} /></label>
    </>}
    {["time", "timetz", "timestamp", "timestamptz", "interval"].includes(props.column.type.name) && <label>Temporal precision<input type="number" value={props.column.type.time_precision ?? ""} onChange={event => props.onEventField("time_precision", event.target.value)} /></label>}
    {props.column.type.name === "enum" && <label>Enum<select value={props.column.type.enum_id ?? ""} onChange={event => props.onEventField("enum_id", event.target.value)}><option value="">Choose enum</option>{props.enums.map(item => <option key={item.id} value={item.id}>{item.name.name}</option>)}</select></label>}
    <label>Array dimensions<input type="number" min="0" value={props.column.type.array_dimensions ?? 0} onChange={event => props.onEventField("array_dimensions", event.target.value)} /></label>
    {/* Column storage rules */}
    <label className="studio-checkbox"><input type="checkbox" checked={props.column.nullable ?? true} onChange={event => props.onEventField("nullable", event.target.checked)} />Nullable</label>
    <label>Default expression<textarea value={props.column.default ?? ""} onChange={event => props.onEventField("default", event.target.value)} /></label>
    {(["smallint", "integer", "bigint"].includes(props.column.type.name) || props.column.identity || props.column.serial) && <label>Generation<select value={generation} onChange={event => props.onEventField("generation", event.target.value)}><option value="none">None</option><option value="serial">Serial</option><option value="by_default">Identity by default</option><option value="always">Identity always</option></select></label>}
    {props.column.identity && <>
      {(["start", "increment", "min_value", "max_value", "cache"] as const).map(field => <label key={field}>{field.replace("_", " ")}<input inputMode="numeric" value={props.column.identity?.[field] ?? ""} onChange={event => props.onEventField(field, event.target.value)} /></label>)}
      <label className="studio-checkbox"><input type="checkbox" checked={props.column.identity.cycle ?? false} onChange={event => props.onEventField("cycle", event.target.checked)} />Cycle</label>
    </>}
    {/* Column description */}
    <label>Description<textarea value={props.column.description ?? ""} onChange={event => props.onEventField("description", event.target.value)} /></label>
  </>;
}

export function OrderedColumns(props: {
  columns: types.Column[];
  selected: string[];
  label: string;
  onEventToggle: (columnId: string) => void;
  onEventMove: (columnId: string, direction: -1 | 1) => void;
}) {
  return <fieldset><legend>{props.label}</legend>
    {props.columns.map(column => <label className="studio-checkbox" key={column.id}><input type="checkbox" checked={props.selected.includes(column.id)} onChange={() => props.onEventToggle(column.id)} />{column.name.name}</label>)}
    <ol>{props.selected.map((id, index) => <li key={id} className="studio-order-row"><span>{index + 1} · {props.columns.find(column => column.id === id)?.name.name}</span><button type="button" className="button" disabled={index === 0} aria-label={`Move ${id} up`} onClick={() => props.onEventMove(id, -1)}>↑</button><button type="button" className="button" disabled={index === props.selected.length - 1} aria-label={`Move ${id} down`} onClick={() => props.onEventMove(id, 1)}>↓</button></li>)}</ol>
  </fieldset>;
}

export function ConstraintFields(props: {
  constraint: editing.RelationalConstraint;
  table: types.Table;
  tables: types.Table[];
  namespaces: types.Namespace[];
  ormMode: boolean;
  ormAlias: string;
  reverseAlias: string;
  cascade: types.OrmRelationship["cascade"];
  onEventField: (field: ConstraintInputField, value: string | boolean) => void;
  onEventToggleColumn: (columnId: string, target: boolean) => void;
  onEventMoveColumn: (columnId: string, direction: -1 | 1, target: boolean) => void;
}) {
  const constraint = props.constraint;
  const target = constraint.kind === "foreign_key" ? props.tables.find(table => table.id === constraint.target_table_id) : undefined;
  if (props.ormMode) return <>
    <label>ORM navigation<input value={props.ormAlias} onChange={event => props.onEventField("orm_alias", event.target.value)} /></label>
    <label>Reverse navigation<input value={props.reverseAlias} onChange={event => props.onEventField("reverse_alias", event.target.value)} /></label>
    <label>ORM cascade<select value={props.cascade ?? "save-update, merge"} onChange={event => props.onEventField("cascade", event.target.value)}><option>save-update, merge</option><option>all</option><option>all, delete-orphan</option></select></label>
  </>;
  return <>
    <label>Name<input value={constraint.name?.name ?? ""} onChange={event => props.onEventField("name", event.target.value)} /></label>
    <label className="studio-checkbox"><input type="checkbox" checked={constraint.name?.quoted ?? false} onChange={event => props.onEventField("quoted", event.target.checked)} />Quoted name</label>
    {constraint.kind === "check" ? <label>Check expression<textarea value={constraint.expression} onChange={event => props.onEventField("expression", event.target.value)} /></label> : <>
      <OrderedColumns label="Source columns" columns={props.table.columns} selected={constraint.column_ids} onEventToggle={id => props.onEventToggleColumn(id, false)} onEventMove={(id, direction) => props.onEventMoveColumn(id, direction, false)} />
      {constraint.kind === "foreign_key" && <>
        <label>Referenced table<select value={constraint.target_table_id} onChange={event => props.onEventField("target_table_id", event.target.value)}>{props.tables.map(table => <option key={table.id} value={table.id}>{props.namespaces.find(item => item.id === table.namespace_id)?.name.name}.{table.name.name}</option>)}</select></label>
        <OrderedColumns label="Target columns" columns={target?.columns ?? []} selected={constraint.target_column_ids} onEventToggle={id => props.onEventToggleColumn(id, true)} onEventMove={(id, direction) => props.onEventMoveColumn(id, direction, true)} />
        <label>On delete<select value={constraint.on_delete ?? "NO ACTION"} onChange={event => props.onEventField("on_delete", event.target.value)}>{actions.map(action => <option key={action}>{action}</option>)}</select></label>
        <label>On update<select value={constraint.on_update ?? "NO ACTION"} onChange={event => props.onEventField("on_update", event.target.value)}>{actions.map(action => <option key={action}>{action}</option>)}</select></label>
        <label>Match<select value={constraint.match ?? "SIMPLE"} onChange={event => props.onEventField("match", event.target.value)}><option>SIMPLE</option><option>FULL</option></select></label>
      </>}
      <label className="studio-checkbox"><input type="checkbox" checked={constraint.deferrable ?? false} onChange={event => props.onEventField("deferrable", event.target.checked)} />Deferrable</label>
      <label className="studio-checkbox"><input type="checkbox" checked={constraint.initially_deferred ?? false} onChange={event => props.onEventField("initially_deferred", event.target.checked)} />Initially deferred</label>
    </>}
  </>;
}

export function IndexFields(props: {
  index: types.Index;
  columns: types.Column[];
  onEventName: (name: string) => void;
  onEventQuoted: (quoted: boolean) => void;
  onEventUnique: (unique: boolean) => void;
  onEventToggleColumn: (columnId: string) => void;
  onEventMoveColumn: (columnId: string, direction: -1 | 1) => void;
}) {
  return <>
    <label>Name<input value={props.index.name.name} onChange={event => props.onEventName(event.target.value)} /></label>
    <label className="studio-checkbox"><input type="checkbox" checked={props.index.name.quoted ?? false} onChange={event => props.onEventQuoted(event.target.checked)} />Quoted name</label>
    <label className="studio-checkbox"><input type="checkbox" checked={props.index.unique ?? false} onChange={event => props.onEventUnique(event.target.checked)} />Unique</label>
    <OrderedColumns label="Index columns" columns={props.columns} selected={props.index.column_ids} onEventToggle={props.onEventToggleColumn} onEventMove={props.onEventMoveColumn} />
  </>;
}

export function NamespaceFields(props: {
  namespace: types.Namespace;
  onEventName: (name: string) => void;
  onEventQuoted: (quoted: boolean) => void;
  onEventDescription: (description: string) => void;
}) {
  return <>
    <label>Name<input value={props.namespace.name.name} onChange={event => props.onEventName(event.target.value)} /></label>
    <label className="studio-checkbox"><input type="checkbox" checked={props.namespace.name.quoted ?? false} onChange={event => props.onEventQuoted(event.target.checked)} />Quoted name</label>
    <label>Description<textarea value={props.namespace.description ?? ""} onChange={event => props.onEventDescription(event.target.value)} /></label>
  </>;
}

export function EnumFields(props: {
  enum: types.EnumType;
  namespaces: types.Namespace[];
  onEventName: (name: string) => void;
  onEventQuoted: (quoted: boolean) => void;
  onEventNamespace: (namespaceId: string) => void;
  onEventLabel: (index: number, value: string) => void;
  onEventAddLabel: () => void;
  onEventDeleteLabel: (index: number) => void;
  onEventDescription: (description: string) => void;
}) {
  return <>
    <label>Namespace<select value={props.enum.namespace_id} onChange={event => props.onEventNamespace(event.target.value)}>{props.namespaces.map(item => <option key={item.id} value={item.id}>{item.name.name}</option>)}</select></label>
    <label>Name<input value={props.enum.name.name} onChange={event => props.onEventName(event.target.value)} /></label>
    <label className="studio-checkbox"><input type="checkbox" checked={props.enum.name.quoted ?? false} onChange={event => props.onEventQuoted(event.target.checked)} />Quoted name</label>
    {props.enum.values.map((value, index) => <div key={index}><label>Label {index + 1}<textarea value={value} onChange={event => props.onEventLabel(index, event.target.value)} /></label><button type="button" className="button" onClick={() => props.onEventDeleteLabel(index)}>Remove label</button></div>)}
    <button type="button" className="button" onClick={props.onEventAddLabel}>Add label</button>
    <label>Description<textarea value={props.enum.description ?? ""} onChange={event => props.onEventDescription(event.target.value)} /></label>
  </>;
}
