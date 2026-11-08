import * as sql from "pgsql-ast-parser";
import * as types from "./relational.types";

export function validateSqlExpressions(table: types.Table): void {
  const columnNames = new Set(table.columns.map(column => column.name.name));
  for (const column of table.columns) {
    if (column.default == null) continue;
    const expression = sql.parse(column.default, "expr");
    const visitor = sql.astVisitor(() => ({
      ref: () => { throw new Error(`${column.id} default must not reference columns`); },
      select: () => { throw new Error("Queries are unsupported in default/check expressions"); },
    }));
    visitor.expr(expression);
  }
  for (const constraint of table.constraints ?? []) {
    if (constraint.kind !== "check") continue;
    const expression = sql.parse(constraint.expression, "expr");
    const visitor = sql.astVisitor(() => ({
      ref: reference => {
        if (reference.table || !columnNames.has(reference.name)) throw new Error(`${constraint.id} check references unknown or qualified column ${reference.name}`);
      },
      select: () => { throw new Error("Queries are unsupported in default/check expressions"); },
    }));
    visitor.expr(expression);
  }
}

export function renameCheckColumn(table: types.Table, oldName: string, newName: string): types.Table {
  const mapper = sql.astMapper(() => ({ ref: reference => reference.name === oldName ? { ...reference, name: newName } : reference }));
  return {
    ...table,
    constraints: (table.constraints ?? []).map(constraint => {
      if (constraint.kind !== "check") return constraint;
      const expression = mapper.expr(sql.parse(constraint.expression, "expr"));
      if (!expression) throw new Error("Renaming removed the check expression");
      return { ...constraint, expression: sql.toSql.expr(expression) };
    }),
  };
}
