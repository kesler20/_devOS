import { DesignNotes } from "./StyledElements";
import * as fields from "./StudioFields";
import * as types from "./relational.types";
import type { EditorDraft, EditorField, StudioMode } from "./StudioState";

// ============================================================ //
//                                                              //
//   STUDIO EDITOR                                              //
//                                                              //
//   Existing floating information card with relational or ORM  //
//   fields. The page owns its draft, selection and validation. //
//   Every control emits an event without persisting state.     //
//                                                              //
// ============================================================ //

export default function StudioEditor(props: {
  draft: EditorDraft;
  document: types.SchemaDocument;
  mode: StudioMode;
  global: boolean;
  onEventField: (field: EditorField, value: string | boolean) => void;
  onEventApply: () => void;
  onEventDelete: () => void;
  onEventClose: () => void;
  onEventAddColumn: (tableId: string) => void;
  onEventMoveColumn: (direction: -1 | 1) => void;
  onEventAddConstraint: (tableId: string, kind: types.KeyConstraint["kind"] | "foreign_key" | "check") => void;
  onEventSelectConstraint: (tableId: string, constraintId: string) => void;
  onEventAddIndex: (tableId: string) => void;
  onEventSelectIndex: (tableId: string, indexId: string) => void;
  onEventToggleKeyColumn: (columnId: string, target: boolean) => void;
  onEventMoveKeyColumn: (columnId: string, direction: -1 | 1, target: boolean) => void;
  onEventSelectCatalog: (catalog: "namespaces" | "enums", id: string) => void;
  onEventAddCatalog: (catalog: "namespaces" | "enums") => void;
  onEventEnumLabel: (index: number, value: string) => void;
  onEventAddEnumLabel: () => void;
  onEventDeleteEnumLabel: (index: number) => void;
}) {
  const draft = props.draft;
  const table = "tableId" in draft ? props.document.tables?.find(item => item.id === draft.tableId) : draft.kind === "table" ? props.document.tables?.find(item => item.id === draft.table.id) : undefined;
  const title = draft.kind === "table" ? draft.table.name.name : draft.kind === "column" ? draft.column.name.name : draft.kind === "constraint" ? draft.constraint.kind.replace("_", " ") : draft.kind === "index" ? "Index" : draft.kind === "namespace" ? "Namespace" : draft.kind === "enum" ? "Enum" : draft.catalog === "namespaces" ? "Namespaces" : "Enums";
  return <DesignNotes className="studio-fields studio-editor nodrag nopan nowheel" role="dialog" aria-label={title} style={props.global ? { position: "fixed", top: "50%", left: "50%", zIndex: 30 } : { zIndex: 30 }}>
    {/* Editor heading */}
    <button type="button" className="studio-close-editor" aria-label="Close editor" onClick={props.onEventClose}>×</button>
    <h3>{title}</h3>
    {/* Table settings and owned objects */}
    {draft.kind === "table" && <>
      <fields.TableFields table={draft.table} namespaces={props.document.namespaces ?? []} ormAlias={draft.ormAlias} color={draft.color} ormMode={props.mode === "orm"} onEventField={props.onEventField} />
      {props.mode === "schema" && <>
        <button type="button" className="button" onClick={() => props.onEventAddColumn(draft.table.id)}>Add column</button>
        <h3>Constraints</h3>
        {(table?.constraints ?? []).map(item => <button type="button" className="button" key={item.id} onClick={() => props.onEventSelectConstraint(draft.table.id, item.id)}>{item.name?.name ?? item.kind.replace("_", " ")}</button>)}
        <div className="studio-editor-actions">{(["primary_key", "unique", "foreign_key", "check"] as const).map(kind => <button type="button" className="button" key={kind} onClick={() => props.onEventAddConstraint(draft.table.id, kind)}>Add {kind.replace("_", " ")}</button>)}</div>
        <h3>Indexes</h3>
        {(table?.indexes ?? []).map(item => <button type="button" className="button" key={item.id} onClick={() => props.onEventSelectIndex(draft.table.id, item.id)}>{item.name.name}</button>)}
        <button type="button" className="button" onClick={() => props.onEventAddIndex(draft.table.id)}>Add index</button>
      </>}
      {props.mode === "orm" && <>
        <h3>Navigation</h3>
        {(table?.constraints ?? []).filter(item => item.kind === "foreign_key").map(item => <button type="button" className="button" key={item.id} onClick={() => props.onEventSelectConstraint(draft.table.id, item.id)}>{item.name?.name ?? item.id}</button>)}
      </>}
    </>}
    {/* Column settings */}
    {draft.kind === "column" && <>
      <fields.ColumnFields column={draft.column} enums={props.document.enums ?? []} ormAlias={draft.ormAlias} ormMode={props.mode === "orm"} onEventField={props.onEventField} />
      {props.mode === "schema" && <div className="studio-editor-actions"><button type="button" className="button" onClick={() => props.onEventMoveColumn(-1)}>Move up</button><button type="button" className="button" onClick={() => props.onEventMoveColumn(1)}>Move down</button></div>}
    </>}
    {/* Constraint settings */}
    {draft.kind === "constraint" && table && <fields.ConstraintFields constraint={draft.constraint} table={table} tables={props.document.tables ?? []} namespaces={props.document.namespaces ?? []} ormMode={props.mode === "orm"} ormAlias={draft.ormAlias} reverseAlias={draft.reverseAlias} cascade={draft.cascade} onEventField={props.onEventField} onEventToggleColumn={props.onEventToggleKeyColumn} onEventMoveColumn={props.onEventMoveKeyColumn} />}
    {/* Index settings */}
    {draft.kind === "index" && table && <fields.IndexFields index={draft.index} columns={table.columns} onEventName={value => props.onEventField("name", value)} onEventQuoted={value => props.onEventField("quoted", value)} onEventUnique={value => props.onEventField("unique", value)} onEventToggleColumn={id => props.onEventToggleKeyColumn(id, false)} onEventMoveColumn={(id, direction) => props.onEventMoveKeyColumn(id, direction, false)} />}
    {/* Namespace settings */}
    {draft.kind === "namespace" && <fields.NamespaceFields namespace={draft.namespace} onEventName={value => props.onEventField("name", value)} onEventQuoted={value => props.onEventField("quoted", value)} onEventDescription={value => props.onEventField("description", value)} />}
    {/* Enum settings */}
    {draft.kind === "enum" && <fields.EnumFields enum={draft.enum} namespaces={props.document.namespaces ?? []} onEventName={value => props.onEventField("name", value)} onEventQuoted={value => props.onEventField("quoted", value)} onEventNamespace={value => props.onEventField("namespace_id", value)} onEventDescription={value => props.onEventField("description", value)} onEventLabel={props.onEventEnumLabel} onEventAddLabel={props.onEventAddEnumLabel} onEventDeleteLabel={props.onEventDeleteEnumLabel} />}
    {/* Catalog selection and editor actions */}
    {draft.kind === "catalog" ? <>
      {(draft.catalog === "namespaces" ? props.document.namespaces ?? [] : props.document.enums ?? []).map(item => <button type="button" className="button" key={item.id} onClick={() => props.onEventSelectCatalog(draft.catalog, item.id)}>{item.name.name}</button>)}
      <button type="button" className="button" onClick={() => props.onEventAddCatalog(draft.catalog)}>Add {draft.catalog === "namespaces" ? "namespace" : "enum"}</button>
    </> : <div className="studio-editor-actions"><button type="button" className="button" onClick={props.onEventApply}>Apply</button><button type="button" className="button" onClick={props.onEventDelete}>{props.mode === "orm" && ["table", "column", "constraint"].includes(draft.kind) ? "Reset mapping" : "Delete"}</button></div>}
  </DesignNotes>;
}
