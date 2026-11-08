import * as React from "react";
import ReactFlow, { Background, Controls, MiniMap, MarkerType, useUpdateNodeInternals, type NodeChange, type ReactFlowInstance, type Connection } from "react-flow-renderer";
import NavbarComponent from "./Navbar";
import { SideBar } from "./StyledElements";
import StudioTable, { type StudioTableData } from "./StudioTable";
import StudioForeignKey from "./StudioForeignKey";
import StudioEditor from "./StudioEditor";
import * as types from "./relational.types";
import * as editing from "./relationalEditing";
import * as diagram from "./relationalDiagram";
import { renderRelationalSql } from "./renderRelationalSql";
import { validateRelational } from "./validateRelational";
import type { EditorDraft, EditorField, StudioMode, StudioFileAction } from "./StudioState";
import "./Studio.css";

const nodeTypes = { relational: StudioTable };
const edgeTypes = { foreignKey: StudioForeignKey };
const version: string = require("../package.json").version;

// ============================================================ //
//                                                              //
//   APP                                                        //
//                                                              //
//   Retains the Studio navigation, canvas and floating editors. //
//   The page owns a portable relational document and UI drafts. //
//   Schema and ORM controls edit separate document sections.   //
//   Open/export actions use local files without a backend.     //
//                                                              //
// ============================================================ //

export default function App() {
  // ====================== //
  //                        //
  //   STATE VARIABLES      //
  //                        //
  // ====================== //
  const [schemaDocument, setSchemaDocument] = React.useState<types.SchemaDocument>(editing.createDocument);
  const [mode, setMode] = React.useState<StudioMode>("schema");
  const [editor, setEditor] = React.useState<EditorDraft>();
  const [inlineNames, setInlineNames] = React.useState<Record<string, string>>({});
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [error, setError] = React.useState("");
  const [viewRequest, setViewRequest] = React.useState<{ tableId?: string; editor?: boolean; viewport?: { x: number; y: number; zoom: number } }>();
  const fileInput = React.useRef<HTMLInputElement>(null);
  const flow = React.useRef<ReactFlowInstance | null>(null);
  const canvas = React.useRef<HTMLDivElement>(null);
  const updateNodeInternals = useUpdateNodeInternals();

  // ====================== //
  //                        //
  //   OBSERVE STATE        //
  //                        //
  // ====================== //
  console.log("schemaDocument", schemaDocument);
  console.log("mode", mode);
  console.log("editor", editor);

  // ====================== //
  //                        //
  //   SIDE EFFECTS         //
  //                        //
  // ====================== //
  React.useEffect(() => {
    const frame = requestAnimationFrame(() => (schemaDocument.tables ?? []).forEach(table => updateNodeInternals(table.id)));
    return () => cancelAnimationFrame(frame);
  }, [schemaDocument.tables, updateNodeInternals]);
  React.useEffect(() => {
    if (!viewRequest || !flow.current) return;
    const frame = requestAnimationFrame(() => {
      if (viewRequest.viewport) flow.current?.setViewport(viewRequest.viewport);
      else {
        const node = viewRequest.tableId ? flow.current?.getNode(viewRequest.tableId) : undefined;
        if (node) flow.current?.setCenter(node.position.x + (viewRequest.editor ? 580 : 290), node.position.y + (node.height || 160) / 2, { zoom: 0.7 });
        else {
          const tables = flow.current?.getNodes() ?? [];
          if (tables.length) {
            const left = Math.min(...tables.map(table => table.position.x));
            const top = Math.min(...tables.map(table => table.position.y));
            const right = Math.max(...tables.map(table => table.position.x + (table.width || 580)));
            const bottom = Math.max(...tables.map(table => table.position.y + (table.height || 100 + table.data.table.columns.length * 55)));
            const zoom = Math.min(0.7, (canvas.current?.clientWidth || 1000) / ((right - left) * 1.4), (canvas.current?.clientHeight || 600) / ((bottom - top) * 1.4));
            flow.current?.setCenter((left + right) / 2, (top + bottom) / 2, { zoom });
          }
        }
      }
      setViewRequest(undefined);
    });
    return () => cancelAnimationFrame(frame);
  }, [viewRequest]);

  // ====================== //
  //                        //
  //   UI EVENT HANDLERS    //
  //                        //
  // ====================== //
  // ------------------------------------------------------ Document
  const handleEventKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") { setEditor(undefined); setMenuOpen(false); }
  };
  const handleEventToggleMenu = () => setMenuOpen(previous => !previous);
  const handleEventCloseEditor = () => setEditor(undefined);
  const handleEventDismissError = () => setError("");
  const handleEventFlowInit = (instance: ReactFlowInstance) => { flow.current = instance; };
  const handleEventEdgeClick = (_event: React.MouseEvent, edge: { source: string; id: string }) => handleEventSelectConstraint(edge.source, edge.id);
  const handleEventFailure = (failure: unknown) => {
    console.error("Studio operation failed", failure);
    setError(failure instanceof Error ? failure.message : String(failure));
  };
  const handleEventMode = (next: StudioMode) => {
    setMode(next);
    setEditor(undefined);
    setInlineNames({});
    setError("");
  };
  const handleEventFileAction = (action: StudioFileAction) => {
    setMenuOpen(false);
    if (mode !== "schema" && (action === "namespaces" || action === "enums")) return;
    if (action === "open") fileInput.current?.click();
    else if (action === "new") {
      setSchemaDocument(editing.createDocument());
      setEditor(undefined);
      setInlineNames({});
      setError("");
      setViewRequest({ viewport: { x: 0, y: 0, zoom: 1 } });
    } else if (action === "namespaces" || action === "enums") setEditor({ kind: "catalog", catalog: action });
    else {
      try {
        const source = action === "export-json" ? editing.exportDocument(schemaDocument) : renderRelationalSql(schemaDocument);
        download(source, action === "export-json" ? "schema.json" : "schema.sql", action === "export-json" ? "application/json" : "text/plain");
        setError("");
      } catch (failure) { handleEventFailure(failure); }
    }
  };
  const handleEventOpenFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = "";
    if (!file) return;
    try {
      const next = editing.openDocument(await file.text());
      setSchemaDocument(next);
      setEditor(undefined);
      setInlineNames({});
      setError("");
      const viewport = next.diagram?.viewport;
      setViewRequest(viewport ? { viewport: { x: viewport.x ?? 0, y: viewport.y ?? 0, zoom: viewport.zoom ?? 1 } } : {});
    } catch (failure) { handleEventFailure(failure); }
  };
  const handleEventNodesChange = (changes: NodeChange[]) => {
    setSchemaDocument(previous => {
      let next = previous;
      for (const change of changes) if (change.type === "position" && change.position) next = diagram.moveTable(next, change.id, change.position.x, change.position.y);
      return next;
    });
  };
  const handleEventViewport = (_event: unknown, viewport: { x: number; y: number; zoom: number }) => {
    setSchemaDocument(previous => diagram.setViewport(previous, viewport.x, viewport.y, viewport.zoom));
  };

  // ------------------------------------------------------ Table
  const handleEventCreateTable = () => {
    if (mode !== "schema") return;
    try {
      const namespace = schemaDocument.namespaces?.[0];
      if (!namespace) throw new Error("Add a namespace before creating a table");
      let number = 1;
      while (schemaDocument.tables?.some(table => table.namespace_id === namespace.id && table.name.name === "table_" + number)) number++;
      const key = crypto.randomUUID();
      const table: types.Table = { id: crypto.randomUUID(), namespace_id: namespace.id, name: { name: "table_" + number }, columns: [{ id: key, name: { name: "id" }, type: { name: "integer" }, nullable: false, identity: { generation: "by_default" } }], constraints: [{ id: crypto.randomUUID(), kind: "primary_key", column_ids: [key] }], indexes: [] };
      const next = editing.replaceTable(schemaDocument, table);
      const color = "#" + [0, 1, 2].map(() => Math.floor(Math.random() * 200).toString(16).padStart(2, "0")).join("");
      setSchemaDocument(validateRelational({ ...next, diagram: { ...next.diagram, tables: [...next.diagram?.tables ?? [], { table_id: table.id, x: 10, y: 10, color }] } }));
      setEditor(undefined);
      setViewRequest({ tableId: table.id });
      setError("");
    } catch (failure) { handleEventFailure(failure); }
  };
  const handleEventSelectTable = (tableId: string) => {
    setViewRequest({ tableId, editor: true });
    if (editor?.kind === "table" && editor.table.id === tableId) { setEditor(undefined); return; }
    const table = getTable(tableId);
    setEditor({ kind: "table", table: structuredClone(table), ormAlias: editing.ormClassName(schemaDocument, table), color: schemaDocument.diagram?.tables?.find(item => item.table_id === tableId)?.color ?? "#aa5df2" });
    setError("");
  };
  const handleEventTableName = (tableId: string, value: string) => { setInlineNames(previous => ({ ...previous, [tableId]: value })); setEditor(undefined); };
  const handleEventCommitTableName = (tableId: string) => {
    const value = inlineNames[tableId];
    if (value === undefined) return;
    try {
      const next = mode === "orm" ? editing.tableAlias(schemaDocument, tableId, value) : editing.replaceTable(schemaDocument, { ...getTable(tableId), name: identifier(value) });
      setSchemaDocument(next);
      clearInline(tableId);
      setError("");
    } catch (failure) { handleEventFailure(failure); }
  };
  const handleEventTableKeyDown = (tableId: string, event: React.KeyboardEvent<HTMLDivElement>) => {
    if ((event.target as HTMLElement).closest(".studio-editor")) return;
    if (event.key === "Enter" && event.shiftKey && event.ctrlKey) { event.preventDefault(); handleEventCreateTable(); }
    else if (event.key === "Enter" && event.shiftKey) { event.preventDefault(); handleEventAddColumn(tableId); }
    else if (event.key === "Backspace" && event.shiftKey && event.ctrlKey && mode === "schema") {
      event.preventDefault();
      try {
        const table = getTable(tableId);
        setSchemaDocument(table.columns.length === 1 ? editing.deleteTable(schemaDocument, tableId) : editing.deleteColumn(schemaDocument, tableId, table.columns[table.columns.length - 1].id));
        setEditor(undefined);
        setError("");
      } catch (failure) { handleEventFailure(failure); }
    } else if (event.key === "Enter" && !event.shiftKey) (event.target as HTMLElement).blur();
  };

  // ------------------------------------------------------ Column
  const handleEventSelectColumn = (tableId: string, columnId: string) => {
    setViewRequest({ tableId, editor: true });
    if (editor?.kind === "column" && editor.column.id === columnId) { setEditor(undefined); return; }
    const column = getColumn(tableId, columnId);
    setEditor({ kind: "column", tableId, column: structuredClone(column), ormAlias: editing.ormAttributeName(schemaDocument, column) });
    setError("");
  };
  const handleEventAddColumn = (tableId: string) => {
    if (mode !== "schema") return;
    const table = getTable(tableId);
    let number = 1;
    while (table.columns.some(column => column.name.name === "column_" + number)) number++;
    const column: types.Column = { id: crypto.randomUUID(), name: { name: "column_" + number }, type: { name: "text" }, nullable: true };
    setSchemaDocument(editing.replaceColumn(schemaDocument, tableId, column));
    setEditor({ kind: "column", tableId, column, ormAlias: column.name.name });
    setError("");
  };
  const handleEventColumnName = (columnId: string, value: string) => { setInlineNames(previous => ({ ...previous, [columnId]: value })); setEditor(undefined); };
  const handleEventCommitColumnName = (tableId: string, columnId: string) => {
    const value = inlineNames[columnId];
    if (value === undefined) return;
    try {
      const next = mode === "orm" ? editing.columnAlias(schemaDocument, columnId, value) : editing.replaceColumn(schemaDocument, tableId, { ...getColumn(tableId, columnId), name: identifier(value) });
      setSchemaDocument(next);
      clearInline(columnId);
      setError("");
    } catch (failure) { handleEventFailure(failure); }
  };
  const handleEventColumnType = (tableId: string, columnId: string, name: types.SqlType["name"]) => {
    const column = getColumn(tableId, columnId);
    const candidate = { ...column, type: changedType(column.type, name) };
    try { setSchemaDocument(editing.replaceColumn(schemaDocument, tableId, candidate)); setEditor(undefined); setError(""); }
    catch (failure) { setEditor({ kind: "column", tableId, column: candidate, ormAlias: editing.ormAttributeName(schemaDocument, column) }); handleEventFailure(failure); }
  };
  const handleEventNullable = (tableId: string, columnId: string, nullable: boolean) => {
    try { setSchemaDocument(editing.replaceColumn(schemaDocument, tableId, { ...getColumn(tableId, columnId), nullable })); setEditor(undefined); setError(""); }
    catch (failure) { handleEventFailure(failure); }
  };
  const handleEventMoveColumn = (direction: -1 | 1) => {
    if (editor?.kind !== "column") return;
    const columns = getTable(editor.tableId).columns.map(item => item.id);
    const from = columns.indexOf(editor.column.id);
    const to = from + direction;
    if (to < 0 || to >= columns.length) return;
    [columns[from], columns[to]] = [columns[to], columns[from]];
    setSchemaDocument(editing.reorderColumns(schemaDocument, editor.tableId, columns));
  };

  // ------------------------------------------------------ Constraint
  const handleEventAddConstraint = (tableId: string, kind: types.KeyConstraint["kind"] | "foreign_key" | "check") => {
    setViewRequest({ tableId, editor: true });
    const id = crypto.randomUUID();
    const constraint: editing.RelationalConstraint = kind === "check" ? { id, kind, expression: "" } : kind === "foreign_key" ? { id, kind, column_ids: [], target_table_id: tableId, target_column_ids: [] } : { id, kind, column_ids: [] };
    setEditor({ kind: "constraint", tableId, constraint, ormAlias: "", reverseAlias: "", cascade: "save-update, merge" });
    setError("");
  };
  const handleEventSelectConstraint = (tableId: string, constraintId: string) => {
    setViewRequest({ tableId, editor: true });
    const table = getTable(tableId);
    const constraint = table.constraints?.find(item => item.id === constraintId);
    if (!constraint) throw new Error("Selected constraint no longer exists");
    const navigation = constraint.kind === "foreign_key" ? editing.navigationNames(schemaDocument, table, constraint) : { attribute_name: "", reverse_attribute_name: "" };
    setEditor({ kind: "constraint", tableId, constraint: structuredClone(constraint), ormAlias: navigation.attribute_name, reverseAlias: navigation.reverse_attribute_name, cascade: schemaDocument.orm?.relationships?.find(item => item.foreign_key_id === constraintId)?.cascade ?? "save-update, merge" });
    setError("");
  };
  const handleEventConnect = (connection: Connection) => {
    if (mode !== "schema" || !connection.source || !connection.target || !connection.sourceHandle || !connection.targetHandle) return;
    setViewRequest({ tableId: connection.source, editor: true });
    setEditor({ kind: "constraint", tableId: connection.source, constraint: { id: crypto.randomUUID(), kind: "foreign_key", column_ids: [connection.sourceHandle], target_table_id: connection.target, target_column_ids: [connection.targetHandle] }, ormAlias: "", reverseAlias: "", cascade: "save-update, merge" });
    setError("");
  };
  const handleEventAddIndex = (tableId: string) => {
    setViewRequest({ tableId, editor: true });
    setEditor({ kind: "index", tableId, index: { id: crypto.randomUUID(), name: { name: "index_" + ((getTable(tableId).indexes?.length ?? 0) + 1) }, column_ids: [], method: "btree" } });
    setError("");
  };
  const handleEventSelectIndex = (tableId: string, indexId: string) => {
    setViewRequest({ tableId, editor: true });
    const index = getTable(tableId).indexes?.find(item => item.id === indexId);
    if (!index) throw new Error("Selected index no longer exists");
    setEditor({ kind: "index", tableId, index: structuredClone(index) });
    setError("");
  };
  const handleEventToggleKeyColumn = (columnId: string, target: boolean) => {
    setEditor(previous => {
      if (previous?.kind === "index") return { ...previous, index: { ...previous.index, column_ids: toggled(previous.index.column_ids, columnId) } };
      if (previous?.kind !== "constraint" || previous.constraint.kind === "check") return previous;
      const constraint = previous.constraint;
      if (target && constraint.kind === "foreign_key") return { ...previous, constraint: { ...constraint, target_column_ids: toggled(constraint.target_column_ids, columnId) } };
      return { ...previous, constraint: { ...constraint, column_ids: toggled(constraint.column_ids, columnId) } };
    });
  };
  const handleEventMoveKeyColumn = (columnId: string, direction: -1 | 1, target: boolean) => {
    setEditor(previous => {
      if (previous?.kind === "index") return { ...previous, index: { ...previous.index, column_ids: moved(previous.index.column_ids, columnId, direction) } };
      if (previous?.kind !== "constraint" || previous.constraint.kind === "check") return previous;
      const constraint = previous.constraint;
      if (target && constraint.kind === "foreign_key") return { ...previous, constraint: { ...constraint, target_column_ids: moved(constraint.target_column_ids, columnId, direction) } };
      return { ...previous, constraint: { ...constraint, column_ids: moved(constraint.column_ids, columnId, direction) } };
    });
  };

  // ------------------------------------------------------ Namespace and Enum
  const handleEventSelectCatalog = (catalog: "namespaces" | "enums", id: string) => {
    if (catalog === "namespaces") {
      const namespace = schemaDocument.namespaces?.find(item => item.id === id);
      if (!namespace) throw new Error("Selected namespace no longer exists");
      setEditor({ kind: "namespace", namespace: structuredClone(namespace) });
    } else {
      const value = schemaDocument.enums?.find(item => item.id === id);
      if (!value) throw new Error("Selected enum no longer exists");
      setEditor({ kind: "enum", enum: structuredClone(value) });
    }
    setError("");
  };
  const handleEventAddCatalog = (catalog: "namespaces" | "enums") => {
    if (catalog === "namespaces") setEditor({ kind: "namespace", namespace: { id: crypto.randomUUID(), name: { name: "schema_" + ((schemaDocument.namespaces?.length ?? 0) + 1) } } });
    else {
      const namespace = schemaDocument.namespaces?.[0];
      if (!namespace) { setError("Add a namespace before creating an enum"); return; }
      setEditor({ kind: "enum", enum: { id: crypto.randomUUID(), namespace_id: namespace.id, name: { name: "enum_" + ((schemaDocument.enums?.length ?? 0) + 1) }, values: ["value"] } });
    }
    setError("");
  };
  const handleEventEnumLabel = (index: number, value: string) => setEditor(previous => previous?.kind === "enum" ? { ...previous, enum: { ...previous.enum, values: previous.enum.values.map((item, position) => position === index ? value : item) } } : previous);
  const handleEventAddEnumLabel = () => setEditor(previous => previous?.kind === "enum" ? { ...previous, enum: { ...previous.enum, values: [...previous.enum.values, ""] } } : previous);
  const handleEventDeleteEnumLabel = (index: number) => setEditor(previous => previous?.kind === "enum" ? { ...previous, enum: { ...previous.enum, values: previous.enum.values.filter((_item, position) => position !== index) } } : previous);

  // ------------------------------------------------------ Editor
  const handleEventEditorField = (field: EditorField, value: string | boolean) => {
    setEditor(previous => {
      if (!previous) return previous;
      if (["orm_alias", "reverse_alias", "color", "cascade"].includes(field)) {
        if (field === "orm_alias" && "ormAlias" in previous) return { ...previous, ormAlias: String(value) };
        if (field === "reverse_alias" && previous.kind === "constraint") return { ...previous, reverseAlias: String(value) };
        if (field === "color" && previous.kind === "table") return { ...previous, color: String(value) };
        if (field === "cascade" && previous.kind === "constraint") return { ...previous, cascade: value as types.OrmRelationship["cascade"] };
      }
      if (previous.kind === "table") {
        const table = previous.table;
        if (field === "name" || field === "quoted") return { ...previous, table: { ...table, name: field === "name" ? { ...table.name, name: String(value) } : { ...table.name, quoted: Boolean(value) } } };
        if (field === "namespace_id") return { ...previous, table: { ...table, namespace_id: String(value) } };
        if (field === "description") return { ...previous, table: { ...table, description: String(value) || null } };
      } else if (previous.kind === "column") {
        const column = previous.column;
        if (field === "name" || field === "quoted") return { ...previous, column: { ...column, name: field === "name" ? { ...column.name, name: String(value) } : { ...column.name, quoted: Boolean(value) } } };
        if (field === "type") return { ...previous, column: { ...column, type: changedType(column.type, value as types.SqlType["name"]) } };
        if (field === "length" || field === "precision" || field === "scale" || field === "time_precision") return { ...previous, column: { ...column, type: { ...column.type, [field]: value === "" ? null : Number(value) } } };
        if (field === "array_dimensions") return { ...previous, column: { ...column, type: { ...column.type, array_dimensions: value === "" ? 0 : Number(value) } } };
        if (field === "enum_id") return { ...previous, column: { ...column, type: { ...column.type, enum_id: String(value) || null } } };
        if (field === "nullable") return { ...previous, column: { ...column, nullable: Boolean(value) } };
        if (field === "default" || field === "description") return { ...previous, column: { ...column, [field]: String(value) || null } };
        if (field === "generation") return { ...previous, column: { ...column, serial: value === "serial", identity: value === "always" || value === "by_default" ? { ...column.identity, generation: value } : null, nullable: value === "none" ? column.nullable : false } };
        if (field === "start" || field === "increment" || field === "min_value" || field === "max_value" || field === "cache") return { ...previous, column: { ...column, identity: { ...column.identity, [field]: String(value) || null } } };
        if (field === "cycle") return { ...previous, column: { ...column, identity: { ...column.identity, cycle: Boolean(value) } } };
      } else if (previous.kind === "constraint") {
        const constraint = previous.constraint;
        if (field === "name") return { ...previous, constraint: { ...constraint, name: value === "" ? null : { ...constraint.name, name: String(value) } } };
        if (field === "quoted") return { ...previous, constraint: { ...constraint, name: { name: constraint.name?.name ?? "", quoted: Boolean(value) } } };
        if (field === "expression" && constraint.kind === "check") return { ...previous, constraint: { ...constraint, expression: String(value) } };
        if (constraint.kind !== "check" && (field === "deferrable" || field === "initially_deferred")) return { ...previous, constraint: { ...constraint, [field]: Boolean(value) } };
        if (constraint.kind === "foreign_key") {
          if (field === "target_table_id") return { ...previous, constraint: { ...constraint, target_table_id: String(value), target_column_ids: [] } };
          if (field === "on_delete" || field === "on_update") return { ...previous, constraint: { ...constraint, [field]: value as types.ForeignKey["on_delete"] } };
          if (field === "match") return { ...previous, constraint: { ...constraint, match: value as types.ForeignKey["match"] } };
        }
      } else if (previous.kind === "index") {
        if (field === "name" || field === "quoted") return { ...previous, index: { ...previous.index, name: field === "name" ? { ...previous.index.name, name: String(value) } : { ...previous.index.name, quoted: Boolean(value) } } };
        if (field === "unique") return { ...previous, index: { ...previous.index, unique: Boolean(value) } };
      } else if (previous.kind === "namespace") {
        if (field === "name" || field === "quoted") return { ...previous, namespace: { ...previous.namespace, name: field === "name" ? { ...previous.namespace.name, name: String(value) } : { ...previous.namespace.name, quoted: Boolean(value) } } };
        if (field === "description") return { ...previous, namespace: { ...previous.namespace, description: String(value) || null } };
      } else if (previous.kind === "enum") {
        if (field === "name" || field === "quoted") return { ...previous, enum: { ...previous.enum, name: field === "name" ? { ...previous.enum.name, name: String(value) } : { ...previous.enum.name, quoted: Boolean(value) } } };
        if (field === "namespace_id") return { ...previous, enum: { ...previous.enum, namespace_id: String(value) } };
        if (field === "description") return { ...previous, enum: { ...previous.enum, description: String(value) || null } };
      }
      throw new Error("Field does not belong to the selected editor");
    });
  };
  const handleEventApplyEditor = () => {
    if (!editor || editor.kind === "catalog") return;
    try {
      let next = schemaDocument;
      if (editor.kind === "table") {
        if (mode === "orm") next = editing.tableAlias(next, editor.table.id, editor.ormAlias);
        else {
          next = editing.replaceTable(next, { ...getTable(editor.table.id), namespace_id: editor.table.namespace_id, name: editor.table.name, description: editor.table.description });
          const positions = next.diagram?.tables ?? [];
          const position = diagram.tablePosition(next, editor.table.id);
          const updated = { table_id: editor.table.id, ...position, color: editor.color };
          next = validateRelational({ ...next, diagram: { ...next.diagram, tables: positions.some(item => item.table_id === editor.table.id) ? positions.map(item => item.table_id === editor.table.id ? updated : item) : [...positions, updated] } });
        }
      } else if (editor.kind === "column") next = mode === "orm" ? editing.columnAlias(next, editor.column.id, editor.ormAlias) : editing.replaceColumn(next, editor.tableId, editor.column);
      else if (editor.kind === "constraint") {
        if (mode === "orm") next = editing.relationshipConfiguration(next, { foreign_key_id: editor.constraint.id, attribute_name: editor.ormAlias, reverse_attribute_name: editor.reverseAlias || null, cascade: editor.cascade });
        else {
          const constraint = editor.constraint;
          if (constraint.kind === "primary_key") next = editing.replaceTable(next, { ...getTable(editor.tableId), columns: getTable(editor.tableId).columns.map(column => constraint.column_ids.includes(column.id) ? { ...column, nullable: false } : column) });
          next = editing.replaceConstraint(next, editor.tableId, constraint);
        }
      } else if (editor.kind === "index") next = editing.replaceIndex(next, editor.tableId, editor.index);
      else if (editor.kind === "namespace") {
        const namespaces = next.namespaces ?? [];
        next = validateRelational({ ...next, namespaces: namespaces.some(item => item.id === editor.namespace.id) ? namespaces.map(item => item.id === editor.namespace.id ? editor.namespace : item) : [...namespaces, editor.namespace] });
      } else if (editor.kind === "enum") {
        const enums = next.enums ?? [];
        next = validateRelational({ ...next, enums: enums.some(item => item.id === editor.enum.id) ? enums.map(item => item.id === editor.enum.id ? editor.enum : item) : [...enums, editor.enum] });
      }
      setSchemaDocument(next);
      setEditor(undefined);
      setError("");
    } catch (failure) { handleEventFailure(failure); }
  };
  const handleEventDeleteEditor = () => {
    if (!editor || editor.kind === "catalog") return;
    try {
      let next = schemaDocument;
      if (editor.kind === "table") next = mode === "orm" ? editing.tableAlias(next, editor.table.id, "") : editing.deleteTable(next, editor.table.id);
      else if (editor.kind === "column") next = mode === "orm" ? editing.columnAlias(next, editor.column.id, "") : editing.deleteColumn(next, editor.tableId, editor.column.id);
      else if (editor.kind === "constraint") next = mode === "orm" ? validateRelational({ ...next, orm: { ...next.orm, relationships: (next.orm?.relationships ?? []).filter(item => item.foreign_key_id !== editor.constraint.id) } }) : editing.deleteConstraint(next, editor.tableId, editor.constraint.id);
      else if (editor.kind === "index") next = editing.deleteIndex(next, editor.tableId, editor.index.id);
      else if (editor.kind === "namespace") next = validateRelational({ ...next, namespaces: (next.namespaces ?? []).filter(item => item.id !== editor.namespace.id) });
      else if (editor.kind === "enum") next = validateRelational({ ...next, enums: (next.enums ?? []).filter(item => item.id !== editor.enum.id) });
      setSchemaDocument(next);
      setEditor(undefined);
      setError("");
    } catch (failure) { handleEventFailure(failure); }
  };

  // ====================== //
  //                        //
  //   UTILS METHODS        //
  //                        //
  // ====================== //
  const getTable = (tableId: string) => {
    const table = schemaDocument.tables?.find(item => item.id === tableId);
    if (!table) throw new Error("Selected table no longer exists");
    return table;
  };
  const getColumn = (tableId: string, columnId: string) => {
    const column = getTable(tableId).columns.find(item => item.id === columnId);
    if (!column) throw new Error("Selected column no longer exists");
    return column;
  };
  const clearInline = (id: string) => setInlineNames(previous => { const next = { ...previous }; delete next[id]; return next; });
  const identifier = (value: string): types.SqlIdentifier => ({ name: value, quoted: !/^[a-z_][a-z0-9_$]*$/.test(value) });
  const changedType = (previous: types.SqlType, name: types.SqlType["name"]): types.SqlType => previous.name === name ? previous : { name, array_dimensions: previous.array_dimensions ?? 0 };
  const toggled = (values: string[], id: string) => values.includes(id) ? values.filter(value => value !== id) : [...values, id];
  const moved = (values: string[], id: string, direction: -1 | 1) => {
    const next = [...values];
    const from = next.indexOf(id);
    const to = from + direction;
    if (from < 0 || to < 0 || to >= next.length) return values;
    [next[from], next[to]] = [next[to], next[from]];
    return next;
  };
  const download = (source: string, name: string, contentType: string) => {
    const url = URL.createObjectURL(new Blob([source], { type: contentType }));
    const anchor = window.document.createElement("a");
    anchor.href = url;
    anchor.download = name;
    anchor.click();
    URL.revokeObjectURL(url);
  };
  const editorTableId = editor?.kind === "table" ? editor.table.id : editor && "tableId" in editor ? editor.tableId : undefined;
  const globalEditor = editor && ["catalog", "namespace", "enum"].includes(editor.kind);
  const editorElement = editor ? <StudioEditor draft={editor} document={schemaDocument} mode={mode} global={Boolean(globalEditor)} onEventField={handleEventEditorField} onEventApply={handleEventApplyEditor} onEventDelete={handleEventDeleteEditor} onEventClose={handleEventCloseEditor} onEventAddColumn={handleEventAddColumn} onEventMoveColumn={handleEventMoveColumn} onEventAddConstraint={handleEventAddConstraint} onEventSelectConstraint={handleEventSelectConstraint} onEventAddIndex={handleEventAddIndex} onEventSelectIndex={handleEventSelectIndex} onEventToggleKeyColumn={handleEventToggleKeyColumn} onEventMoveKeyColumn={handleEventMoveKeyColumn} onEventSelectCatalog={handleEventSelectCatalog} onEventAddCatalog={handleEventAddCatalog} onEventEnumLabel={handleEventEnumLabel} onEventAddEnumLabel={handleEventAddEnumLabel} onEventDeleteEnumLabel={handleEventDeleteEnumLabel} /> : undefined;
  const nodes = (schemaDocument.tables ?? []).map(table => {
    const data: StudioTableData = {
      table, qualifiedName: (schemaDocument.namespaces?.find(item => item.id === table.namespace_id)?.name.name ?? "") + "." + table.name.name,
      headerName: inlineNames[table.id] ?? (mode === "orm" ? editing.ormClassName(schemaDocument, table) : table.name.name),
      columnNames: Object.fromEntries(table.columns.map(column => [column.id, inlineNames[column.id] ?? (mode === "orm" ? editing.ormAttributeName(schemaDocument, column) : column.name.name)])),
      color: schemaDocument.diagram?.tables?.find(item => item.table_id === table.id)?.color ?? "#aa5df2", ormMode: mode === "orm", editor: editorTableId === table.id ? editorElement : undefined,
      onEventTableName: handleEventTableName, onEventCommitTableName: handleEventCommitTableName, onEventColumnName: handleEventColumnName, onEventCommitColumnName: handleEventCommitColumnName, onEventColumnType: handleEventColumnType, onEventNullable: handleEventNullable, onEventSelectTable: handleEventSelectTable, onEventSelectColumn: handleEventSelectColumn, onEventKeyDown: handleEventTableKeyDown,
    };
    return { id: table.id, type: "relational", position: diagram.tablePosition(schemaDocument, table.id), data };
  });
  const edges = diagram.foreignKeyEdges(schemaDocument);

  // ====================== //
  //                        //
  //   UI COMPONENTS        //
  //                        //
  // ====================== //
  return <div onKeyDown={handleEventKeyDown}>
    {/* Navigation */}
    <section className="studio-nav"><NavbarComponent version={version} menuOpen={menuOpen} canCreateTable={mode === "schema"} onEventToggleMenu={handleEventToggleMenu} onEventFileAction={handleEventFileAction} onEventCreateTable={handleEventCreateTable} /></section>
    <input ref={fileInput} type="file" accept=".json,application/json" hidden aria-label="Open relational document" onChange={handleEventOpenFile} />
    {/* Document sections */}
    <section style={{ margin: "0 20%", height: 56 }}><SideBar style={{ height: "100%" }}>
      <button type="button" className="studio-section-tab" aria-pressed={mode === "schema"} onClick={() => handleEventMode("schema")}>Relational Schema<svg width="36" height="36" viewBox="0 0 36 36" fill="currentColor"><path d="M9 1h10v10H9zM9 14h10v10H9zM9 27h10v9H9zM26 14h10v10H26z" /><path d="M13 8h3v22h-3zM14 17h16v3H14z" /></svg></button>
      <button type="button" className="studio-section-tab" aria-pressed={mode === "orm"} onClick={() => handleEventMode("orm")}>ORM Configuration<svg width="30" height="30" viewBox="0 0 30 30" fill="none" stroke="currentColor" strokeWidth="1.4"><rect x="1" y="1" width="28" height="28" rx="2" /><path d="M10 1v28M1 10h28M1 20h28" /></svg></button>
    </SideBar></section>
    {/* Canvas */}
    <section style={{ margin: "0 1.5%" }}><div ref={canvas} className="data-model-canvas" style={{ height: "calc(100vh - 138px)" }}>
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} onNodesChange={handleEventNodesChange} onConnect={handleEventConnect} onEdgeClick={handleEventEdgeClick} onMoveEnd={handleEventViewport} onInit={handleEventFlowInit} defaultEdgeOptions={{ markerEnd: { type: MarkerType.ArrowClosed } }} deleteKeyCode={null}>
        <Background /><Controls /><MiniMap />
      </ReactFlow>
    </div></section>
    {/* Document metadata and validation */}
    {globalEditor && editorElement}
    {error && <div className="studio-error" role="alert">{error}<button type="button" className="button" aria-label="Dismiss error" onClick={handleEventDismissError}>×</button></div>}
  </div>;
}
