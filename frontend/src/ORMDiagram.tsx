import * as React from "react";
import { Handle, Position, type NodeProps } from "react-flow-renderer";
import { FaPlus } from "react-icons/fa6";
import ModalCard from "./ModalCard";

// ======================= //
//                         //
//   TYPE DEFINITIONS      //
//                         //
// ======================= //

type RowField = "required" | "name" | "type";

export type ORMKeyBehavior =
  | "auto_increment"
  | "ondelete_cascade"
  | "ondelete_set_null"
  | "ondelete_restrict";

export type ORMKeyType = {
  type: "primary_key" | "foreign_key";
  behaviors: ORMKeyBehavior[];
  table?: string;
  column?: string;
};

export type ORMLinkedProperty = {
  table: string;
  property: string;
  cascade?: string;
  order_by?: string;
  foreign_key?: string;
};

export type ORMManyToManyConfig = {
  association_table: string;
  self_referential: boolean;
  left_column?: string;
  right_column?: string;
  primaryjoin?: string;
  secondaryjoin?: string;
};

export type ORMRow = {
  name: string;
  type: string;
  description: string;
  required: boolean;
  default_value?: string;
  enum_name?: string;
  key_type?: ORMKeyType;
  linked_property?: ORMLinkedProperty;
  many_to_many?: ORMManyToManyConfig;
};

export type ORMNodeData = {
  name: string;
  table_name: string;
  description: string;
  color: string;
  properties: ORMRow[];
  currentRowIndex: number;
  modalMode: "table" | "row" | null;
  is_association_table?: boolean;
  unique_constraints?: string[][];
};

// ======================= //
//                         //
//     MAIN COMPONENT      //
//                         //
// ======================= //

export default function ORMDiagram({
  id,
  data,
}: NodeProps<
  ORMNodeData & {
    onEventAddRow: (nodeId: string) => void;
    onEventDeleteRow: (nodeId: string) => void;
    onEventToggleRowModal: (nodeId: string, rowIndex: number) => void;
    onEventToggleTableModal: (nodeId: string) => void;
    onEventUpdateObjectName: (nodeId: string, name: string) => void;
    onEventUpdateTableName: (nodeId: string, tableName: string) => void;
    onEventUpdateObjectComment: (nodeId: string, description: string) => void;
    onEventUpdateRowField: (
      nodeId: string,
      rowIndex: number,
      field: RowField,
      value: string
    ) => void;
    onEventUpdateRowDescription: (
      nodeId: string,
      rowIndex: number,
      description: string
    ) => void;
    onEventUpdateRowKeyType: (
      nodeId: string,
      rowIndex: number,
      keyType: "none" | "primary_key" | "foreign_key"
    ) => void;
    onEventToggleRowBehavior: (
      nodeId: string,
      rowIndex: number,
      behavior: ORMKeyBehavior
    ) => void;
    onEventUpdateManyToManyConfig: (
      nodeId: string,
      rowIndex: number,
      field: keyof ORMManyToManyConfig,
      value: string | boolean
    ) => void;
    onEventUpdateRowDefaultValue: (
      nodeId: string,
      rowIndex: number,
      defaultValue: string
    ) => void;
    onEventUpdateRowEnumName: (
      nodeId: string,
      rowIndex: number,
      enumName: string
    ) => void;
    onEventUpdateLinkedPropertyField: (
      nodeId: string,
      rowIndex: number,
      field: keyof ORMLinkedProperty,
      value: string
    ) => void;
    onEventCreateTable: () => void;
    onEventToggleAssociationTable: (nodeId: string) => void;
    onEventAddUniqueConstraint: (nodeId: string) => void;
    onEventRemoveUniqueConstraint: (nodeId: string, constraintIndex: number) => void;
    onEventUpdateUniqueConstraint: (
      nodeId: string,
      constraintIndex: number,
      value: string
    ) => void;
    allNodes: { id: string; name: string; table_name: string }[];
  }
>) {
  // ==================== //
  //                      //
  //   EVENT HANDLERS     //
  //                      //
  // ==================== //

  const handleModifyTable = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter" && event.shiftKey && event.ctrlKey) {
      event.preventDefault();
      data.onEventCreateTable();
    } else if (event.key === "Enter" && event.shiftKey) {
      event.preventDefault();
      data.onEventAddRow(id);
    } else if (event.key === "Backspace" && event.shiftKey && event.ctrlKey) {
      event.preventDefault();
      data.onEventDeleteRow(id);
    }
  };

  // ==================== //
  //                      //
  //   RENDERING          //
  //                      //
  // ==================== //

  const isAssociationTable = data.is_association_table ?? false;
  const borderColor = isAssociationTable ? "#ff9800" : data.color;
  const headerLabel = isAssociationTable ? "⬡ Association Table" : null;

  return (
    <div
      className="diagram"
      style={{
        top: 285,
        left: 534,
        border: isAssociationTable ? "3px dashed #ff9800" : undefined,
        borderRadius: isAssociationTable ? "8px" : undefined,
      }}
      onKeyDown={handleModifyTable}
    >
      {data.modalMode && (
        <ModalCard
          nodeId={id}
          currentRowIndex={data.currentRowIndex}
          modalMode={data.modalMode}
          objectName={data.name}
          tableName={data.table_name}
          objectDescription={data.description}
          properties={data.properties}
          isAssociationTable={isAssociationTable}
          uniqueConstraints={data.unique_constraints}
          allNodes={data.allNodes}
          onEventUpdateTableName={data.onEventUpdateTableName}
          onEventUpdateObjectComment={data.onEventUpdateObjectComment}
          onEventUpdateRowDescription={data.onEventUpdateRowDescription}
          onEventUpdateRowKeyType={data.onEventUpdateRowKeyType}
          onEventToggleRowBehavior={data.onEventToggleRowBehavior}
          onEventUpdateManyToManyConfig={data.onEventUpdateManyToManyConfig}
          onEventUpdateRowDefaultValue={data.onEventUpdateRowDefaultValue}
          onEventUpdateRowEnumName={data.onEventUpdateRowEnumName}
          onEventUpdateLinkedPropertyField={data.onEventUpdateLinkedPropertyField}
          onEventToggleAssociationTable={data.onEventToggleAssociationTable}
          onEventAddUniqueConstraint={data.onEventAddUniqueConstraint}
          onEventRemoveUniqueConstraint={data.onEventRemoveUniqueConstraint}
          onEventUpdateUniqueConstraint={data.onEventUpdateUniqueConstraint}
        />
      )}

      <>
        {data.properties.map((_, index) => {
          const offSet = index * 50 + (isAssociationTable ? 130 : 100);
          return (
            <Handle
              key={`target-${index}`}
              type="target"
              id={`row-${index}`}
              position={Position.Left}
              style={{
                width: 20,
                height: 20,
                top: offSet,
                backgroundColor: "green",
              }}
            />
          );
        })}

        {headerLabel && (
          <div
            style={{
              backgroundColor: "#ff9800",
              color: "white",
              padding: "4px 8px",
              fontSize: "11px",
              fontWeight: "bold",
              textAlign: "center",
              borderRadius: "4px 4px 0 0",
              marginBottom: "-4px",
            }}
          >
            {headerLabel}
          </div>
        )}

        <div className="object-name-row">
          <input
            type="text"
            value={data.name}
            onChange={(event) =>
              data.onEventUpdateObjectName(id, event.target.value)
            }
            className="object-name"
            style={{
              borderTop: `20px solid ${borderColor}`,
            }}
          />
          <button
            type="button"
            className="table-meta-btn"
            onClick={() => data.onEventToggleTableModal(id)}
          >
            i
          </button>
        </div>
        <div className="table-name">({data.table_name})</div>

        <div className="grid-table">
          {data.properties.map((inputElement, index) => {
            return (
              <>
                <select
                  value={inputElement.required ? "required" : "nullable"}
                  onChange={(event) =>
                    data.onEventUpdateRowField(
                      id,
                      index,
                      "required",
                      event.target.value
                    )
                  }
                >
                  <option value="required">required</option>
                  <option value="nullable">nullable</option>
                </select>
                <input
                  placeholder={inputElement.name}
                  value={inputElement.name}
                  onChange={(event) =>
                    data.onEventUpdateRowField(id, index, "name", event.target.value)
                  }
                />
                <select
                  value={inputElement.type}
                  onChange={(event) =>
                    data.onEventUpdateRowField(id, index, "type", event.target.value)
                  }
                >
                  <option value="int">int</option>
                  <option value="str">str</option>
                  <option value="text">text</option>
                  <option value="bool">bool</option>
                  <option value="float">float</option>
                  <option value="datetime">datetime</option>
                  <option value="enum">enum</option>
                  <option value="array">array</option>
                  <option value="object">object</option>
                  <option value="many_to_many">many_to_many</option>
                </select>
                <div className="arrowBtn">
                  <FaPlus onClick={() => data.onEventToggleRowModal(id, index)} />
                </div>
              </>
            );
          })}
        </div>

        {data.properties.map((_, index) => {
          const offSet = index * 50 + (isAssociationTable ? 130 : 100);
          return (
            <Handle
              key={`source-${index}`}
              type="source"
              id={`row-${index}`}
              position={Position.Right}
              style={{
                width: 20,
                height: 20,
                top: offSet,
                backgroundColor: "yellow",
              }}
            />
          );
        })}
      </>
    </div>
  );
}
