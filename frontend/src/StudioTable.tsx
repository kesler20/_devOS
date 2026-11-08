import * as React from "react";
import { Handle, Position, type NodeProps } from "react-flow-renderer";
import { FaPlus } from "react-icons/fa6";
import * as types from "./relational.types";

// ============================================================ //
//                                                              //
//   STUDIO TABLE                                               //
//                                                              //
//   Retains the Studio table strip, teal name and inline rows. //
//   Stable column handles represent physical foreign keys.    //
//   The page owns drafts, edits and the floating information UI. //
//                                                              //
// ============================================================ //

export type StudioTableData = {
  table: types.Table;
  qualifiedName: string;
  headerName: string;
  columnNames: Record<string, string>;
  color: string;
  ormMode: boolean;
  editor?: React.ReactNode;
  onEventTableName: (tableId: string, value: string) => void;
  onEventCommitTableName: (tableId: string) => void;
  onEventColumnName: (columnId: string, value: string) => void;
  onEventCommitColumnName: (tableId: string, columnId: string) => void;
  onEventColumnType: (tableId: string, columnId: string, value: types.SqlType["name"]) => void;
  onEventNullable: (tableId: string, columnId: string, value: boolean) => void;
  onEventSelectTable: (tableId: string) => void;
  onEventSelectColumn: (tableId: string, columnId: string) => void;
  onEventKeyDown: (tableId: string, event: React.KeyboardEvent<HTMLDivElement>) => void;
};



export default function StudioTable({ data }: NodeProps<StudioTableData>) {
  return <div className="diagram" onKeyDown={event => data.onEventKeyDown(data.table.id, event)}>
    {/* Floating information editor */}
    {data.editor}
    {/* Table heading */}
    <div className="object-name-row">
      <div className="studio-table-heading">
        <div className="studio-table-grip" aria-label={`Move table ${data.table.id}`} title="Drag to move table" style={{ backgroundColor: data.color }} />
        <input className="object-name nodrag" aria-label={`Table name ${data.table.id}`} value={data.headerName} onChange={event => data.onEventTableName(data.table.id, event.target.value)} onBlur={() => data.onEventCommitTableName(data.table.id)} />
      </div>
      <button type="button" className="table-meta-btn nodrag" aria-label={`Table information ${data.table.id}`} onClick={() => data.onEventSelectTable(data.table.id)}>i</button>
    </div>
    <div className="table-name">({data.qualifiedName})</div>
    {/* Ordered physical columns */}
    <div className="grid-table studio-rows">
      {data.table.columns.map(column => <div className="studio-table-row" key={column.id}>
        <Handle type="target" position={Position.Left} id={column.id} style={{ width: 20, height: 20, top: "50%", backgroundColor: "green" }} />
        <select className="nodrag" aria-label={`Nullability ${column.id}`} value={(column.nullable ?? true) ? "nullable" : "required"} disabled={data.ormMode} onChange={event => data.onEventNullable(data.table.id, column.id, event.target.value === "nullable")}><option value="required">required</option><option value="nullable">nullable</option></select>
        <div className="studio-column-name">
          <input className="nodrag" aria-label={`Column name ${column.id}`} value={data.columnNames[column.id]} onChange={event => data.onEventColumnName(column.id, event.target.value)} onBlur={() => data.onEventCommitColumnName(data.table.id, column.id)} />
          <span className="studio-key-label">{(data.table.constraints ?? []).filter(item => item.kind !== "check" && item.column_ids.includes(column.id)).map(item => item.kind === "primary_key" ? "PK" : item.kind === "unique" ? "UQ" : "FK").filter((value, index, array) => array.indexOf(value) === index).join(" ")}</span>
        </div>
        <select className="nodrag" aria-label={`Column type ${column.id}`} value={column.type.name} disabled={data.ormMode} onChange={event => data.onEventColumnType(data.table.id, column.id, event.target.value as types.SqlType["name"])}>
          {types.sqlTypeNames.map(name => <option key={name} value={name}>{name}{name === column.type.name ? "[]".repeat(column.type.array_dimensions ?? 0) : ""}</option>)}
        </select>
        <button type="button" className="arrowBtn nodrag" aria-label={`Column information ${column.id}`} onClick={() => data.onEventSelectColumn(data.table.id, column.id)}><FaPlus /></button>
        <Handle type="source" position={Position.Right} id={column.id} style={{ width: 20, height: 20, top: "50%", backgroundColor: "yellow" }} />
      </div>)}
    </div>
  </div>;
}
