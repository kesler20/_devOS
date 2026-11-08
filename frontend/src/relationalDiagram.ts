import type { Edge } from "react-flow-renderer";
import * as types from "./relational.types";
import { validateRelational } from "./validateRelational";

export type ForeignKeyEdgeData = {
  constraint: types.ForeignKey;
  lane: number;
  loopTop: number;
};

export function tablePosition(document: types.SchemaDocument, tableId: string): { x: number; y: number } {
  const saved = document.diagram?.tables?.find(item => item.table_id === tableId);
  if (saved) return { x: saved.x, y: saved.y };
  const index = (document.tables ?? []).findIndex(item => item.id === tableId);
  if (index < 0) throw new Error("Diagram refers to a missing table");
  const rowHeight = Math.max(0, ...(document.tables ?? []).map(table => table.columns.length)) * 55 + 180;
  return { x: 60 + (index % 3) * 760, y: 60 + Math.floor(index / 3) * rowHeight };
}

export function foreignKeyEdges(document: types.SchemaDocument): Array<Edge<ForeignKeyEdgeData>> {
  validateRelational(document);
  const tables = document.tables ?? [];
  const lanes = new Map<string, number>();
  const edges: Array<Edge<ForeignKeyEdgeData>> = [];
  for (const table of tables) {
    for (const constraint of table.constraints ?? []) {
      if (constraint.kind !== "foreign_key") continue;
      const target = tables.find(item => item.id === constraint.target_table_id);
      if (!target) throw new Error("Foreign key target table is missing");
      const group = JSON.stringify([table.id, target.id].sort());
      const lane = lanes.get(group) ?? 0;
      lanes.set(group, lane + 1);
      const sourceNames = constraint.column_ids.map(id => table.columns.find(item => item.id === id)!.name.name);
      const targetNames = constraint.target_column_ids.map(id => target.columns.find(item => item.id === id)!.name.name);
      const pairs = sourceNames.join(", ") + " → " + targetNames.join(", ");
      edges.push({
        id: constraint.id,
        source: table.id,
        target: target.id,
        sourceHandle: constraint.column_ids[0],
        targetHandle: constraint.target_column_ids[0],
        type: "foreignKey",
        label: constraint.name ? constraint.name.name + " · " + pairs : pairs,
        data: { constraint, lane, loopTop: tablePosition(document, table.id).y - 45 - lane * 35 },
      });
    }
  }
  return edges;
}

export function moveTable(document: types.SchemaDocument, tableId: string, x: number, y: number): types.SchemaDocument {
  const tables = document.diagram?.tables ?? [];
  const position = tables.find(item => item.table_id === tableId);
  const updated = position ? tables.map(item => item.table_id === tableId ? { ...item, x, y } : item) : [...tables, { table_id: tableId, x, y }];
  return validateRelational({ ...document, diagram: { ...document.diagram, tables: updated } });
}

export function setViewport(document: types.SchemaDocument, x: number, y: number, zoom: number): types.SchemaDocument {
  return validateRelational({ ...document, diagram: { ...document.diagram, viewport: { x, y, zoom } } });
}
