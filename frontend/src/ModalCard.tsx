import { Badge, DesignNotes, CheckBoxElement } from "./StyledElements";

// ======================= //
//                         //
//   TYPE DEFINITIONS      //
//                         //
// ======================= //

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

// ======================= //
//                         //
//     SUBCOMPONENTS       //
//                         //
// ======================= //

function CheckBox(props: {
  label: string;
  checked: boolean;
  onEventToggle: () => void;
}) {
  return (
    <CheckBoxElement>
      <label className="container">
        <input type="checkbox" checked={props.checked} readOnly />
        <span className="checkmark" onClick={props.onEventToggle}></span>
        <p>{props.label}</p>
      </label>
    </CheckBoxElement>
  );
}

// ======================= //
//                         //
//     MAIN COMPONENT      //
//                         //
// ======================= //

export default function ModalCard(props: {
  nodeId: string;
  currentRowIndex: number;
  modalMode: "table" | "row";
  objectName: string;
  tableName: string;
  objectDescription: string;
  properties: ORMRow[];
  isAssociationTable: boolean;
  uniqueConstraints?: string[][];
  allNodes: { id: string; name: string; table_name: string }[];
  onEventUpdateTableName: (nodeId: string, tableName: string) => void;
  onEventUpdateObjectComment: (nodeId: string, description: string) => void;
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
  onEventToggleAssociationTable: (nodeId: string) => void;
  onEventAddUniqueConstraint: (nodeId: string) => void;
  onEventRemoveUniqueConstraint: (nodeId: string, constraintIndex: number) => void;
  onEventUpdateUniqueConstraint: (
    nodeId: string,
    constraintIndex: number,
    value: string
  ) => void;
}) {
  const currentRow = props.properties[props.currentRowIndex];
  const currentRowName = currentRow?.name ?? "field";
  const currentRowType = currentRow?.type ?? "str";
  const keyType = currentRow?.key_type?.type ?? "none";
  const rowDescription = currentRow?.description ?? "";
  const behaviors = currentRow?.key_type?.behaviors ?? [];
  const manyToMany = currentRow?.many_to_many;
  const linkedProperty = currentRow?.linked_property;
  const defaultValue = currentRow?.default_value ?? "";
  const enumName = currentRow?.enum_name ?? "";
  const isRelationshipType = ["array", "object"].includes(currentRowType);

  // ==================== //
  //                      //
  //   RENDERING          //
  //                      //
  // ==================== //

  return (
    <DesignNotes>
      <h3>{props.modalMode === "table" ? props.objectName : currentRowName}</h3>
      <div className="flex-row-start">
        <Badge>
          <img
            src="https://uploads-ssl.webflow.com/612b579592e3bf93283444b6/612b69f61d22d5ca878550af_chevron-right.svg"
            loading="lazy"
            alt=""
            className="image-2-copy-copy"
          />
        </Badge>
        <p
          style={{
            color: "rgb(108, 108, 108)",
          }}
        >
          {props.modalMode === "table" ? "Table metadata" : "Field metadata"}
        </p>
      </div>
      {props.modalMode === "table" ? (
        <>
          <div className="margin-small">
            <input
              value={props.tableName}
              onChange={(e) =>
                props.onEventUpdateTableName(props.nodeId, e.target.value)
              }
              placeholder="table_name"
            />
          </div>
          <textarea
            className="class"
            value={props.objectDescription}
            onChange={(e) =>
              props.onEventUpdateObjectComment(props.nodeId, e.target.value)
            }
          />
          <div style={{ marginTop: "10px", width: "100%" }}>
            <CheckBox
              label="Association Table"
              checked={props.isAssociationTable}
              onEventToggle={() => props.onEventToggleAssociationTable(props.nodeId)}
            />
          </div>
          <div style={{ marginTop: "15px", width: "100%" }}>
            <p
              style={{
                color: "rgb(108, 108, 108)",
                marginBottom: "8px",
                fontWeight: "bold",
              }}
            >
              Unique Constraints
            </p>
            {(props.uniqueConstraints || []).map((constraint, index) => (
              <div
                key={index}
                style={{ display: "flex", gap: "5px", marginBottom: "5px" }}
              >
                <input
                  value={constraint.join(", ")}
                  onChange={(e) =>
                    props.onEventUpdateUniqueConstraint(
                      props.nodeId,
                      index,
                      e.target.value
                    )
                  }
                  placeholder="Enter column names (comma-separated)"
                  style={{ flex: 1 }}
                />
                <button
                  onClick={() =>
                    props.onEventRemoveUniqueConstraint(props.nodeId, index)
                  }
                  style={{
                    padding: "5px 10px",
                    backgroundColor: "#f44336",
                    color: "white",
                    border: "none",
                    borderRadius: "3px",
                    cursor: "pointer",
                  }}
                >
                  ✕
                </button>
              </div>
            ))}
            <button
              className="button"
              onClick={() => props.onEventAddUniqueConstraint(props.nodeId)}
            >
              + Add Constraint
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="margin-small">
            <select
              value={keyType}
              onChange={(e) =>
                props.onEventUpdateRowKeyType(
                  props.nodeId,
                  props.currentRowIndex,
                  e.target.value as "none" | "primary_key" | "foreign_key"
                )
              }
            >
              <option value="none">no key</option>
              <option value="primary_key">primary key</option>
              <option value="foreign_key">foreign key</option>
            </select>
          </div>
          <textarea
            className="class"
            value={rowDescription}
            onChange={(e) =>
              props.onEventUpdateRowDescription(
                props.nodeId,
                props.currentRowIndex,
                e.target.value
              )
            }
          />

          {/* Default Value - for scalar types */}
          {!isRelationshipType && currentRowType !== "many_to_many" && (
            <div className="margin-small" style={{ width: "100%" }}>
              <label style={{ fontSize: "11px", color: "#666" }}>
                Default Value
              </label>
              <input
                value={defaultValue}
                onChange={(e) =>
                  props.onEventUpdateRowDefaultValue(
                    props.nodeId,
                    props.currentRowIndex,
                    e.target.value
                  )
                }
                placeholder='e.g., "0", "False", "lambda: datetime.now(UTC)"'
                style={{ marginTop: "4px", width: "100%" }}
              />
            </div>
          )}

          {/* Enum Name - when type is enum */}
          {currentRowType === "enum" && (
            <div className="margin-small" style={{ width: "100%" }}>
              <label style={{ fontSize: "11px", color: "#666" }}>
                Enum Class Name
              </label>
              <input
                value={enumName}
                onChange={(e) =>
                  props.onEventUpdateRowEnumName(
                    props.nodeId,
                    props.currentRowIndex,
                    e.target.value
                  )
                }
                placeholder="e.g., QuestionnaireStatus"
                style={{ marginTop: "4px", width: "100%" }}
              />
            </div>
          )}

          {keyType == "primary_key" && (
            <div className="flex-column-start">
              <CheckBox
                label="auto increment"
                checked={behaviors.includes("auto_increment")}
                onEventToggle={() =>
                  props.onEventToggleRowBehavior(
                    props.nodeId,
                    props.currentRowIndex,
                    "auto_increment"
                  )
                }
              />
            </div>
          )}

          {keyType == "foreign_key" && (
            <div className="flex-column-start">
              <p style={{ fontSize: "11px", color: "#666", marginBottom: "5px" }}>
                On Delete Behavior
              </p>
              <CheckBox
                label="CASCADE"
                checked={behaviors.includes("ondelete_cascade")}
                onEventToggle={() =>
                  props.onEventToggleRowBehavior(
                    props.nodeId,
                    props.currentRowIndex,
                    "ondelete_cascade"
                  )
                }
              />
              <CheckBox
                label="SET NULL"
                checked={behaviors.includes("ondelete_set_null")}
                onEventToggle={() =>
                  props.onEventToggleRowBehavior(
                    props.nodeId,
                    props.currentRowIndex,
                    "ondelete_set_null"
                  )
                }
              />
              <CheckBox
                label="RESTRICT"
                checked={behaviors.includes("ondelete_restrict")}
                onEventToggle={() =>
                  props.onEventToggleRowBehavior(
                    props.nodeId,
                    props.currentRowIndex,
                    "ondelete_restrict"
                  )
                }
              />
            </div>
          )}

          {/* Relationship Properties - for array/object types */}
          {isRelationshipType && linkedProperty && (
            <div className="flex-column-start" style={{ marginTop: "10px" }}>
              <p
                style={{
                  color: "rgb(108, 108, 108)",
                  marginBottom: "5px",
                  fontWeight: "bold",
                }}
              >
                Relationship Options
              </p>
              <div className="margin-small" style={{ width: "100%" }}>
                <label style={{ fontSize: "11px", color: "#666" }}>Cascade</label>
                <input
                  value={linkedProperty.cascade ?? ""}
                  onChange={(e) =>
                    props.onEventUpdateLinkedPropertyField(
                      props.nodeId,
                      props.currentRowIndex,
                      "cascade",
                      e.target.value
                    )
                  }
                  placeholder='e.g., "all, delete-orphan"'
                  style={{ marginTop: "4px", width: "100%" }}
                />
              </div>
              <div className="margin-small" style={{ width: "100%" }}>
                <label style={{ fontSize: "11px", color: "#666" }}>Order By</label>
                <input
                  value={linkedProperty.order_by ?? ""}
                  onChange={(e) =>
                    props.onEventUpdateLinkedPropertyField(
                      props.nodeId,
                      props.currentRowIndex,
                      "order_by",
                      e.target.value
                    )
                  }
                  placeholder="e.g., Question.order.asc()"
                  style={{ marginTop: "4px", width: "100%" }}
                />
              </div>
              <div className="margin-small" style={{ width: "100%" }}>
                <label style={{ fontSize: "11px", color: "#666" }}>
                  Foreign Key
                </label>
                <input
                  value={linkedProperty.foreign_key ?? ""}
                  onChange={(e) =>
                    props.onEventUpdateLinkedPropertyField(
                      props.nodeId,
                      props.currentRowIndex,
                      "foreign_key",
                      e.target.value
                    )
                  }
                  placeholder="e.g., Question.questionnaire_id"
                  style={{ marginTop: "4px", width: "100%" }}
                />
              </div>
            </div>
          )}

          {currentRowType === "many_to_many" && (
            <div className="flex-column-start" style={{ marginTop: "10px" }}>
              <p
                style={{
                  color: "rgb(108, 108, 108)",
                  marginBottom: "5px",
                  fontWeight: "bold",
                }}
              >
                Many-to-Many Configuration
              </p>
              <div className="margin-small" style={{ width: "100%" }}>
                <label style={{ fontSize: "11px", color: "#666" }}>
                  Association Table
                </label>
                <input
                  value={manyToMany?.association_table ?? ""}
                  onChange={(e) =>
                    props.onEventUpdateManyToManyConfig(
                      props.nodeId,
                      props.currentRowIndex,
                      "association_table",
                      e.target.value
                    )
                  }
                  placeholder="Enter: association table name"
                  style={{ marginTop: "4px", width: "100%" }}
                />
              </div>

              <div style={{ marginTop: "8px", width: "100%" }}>
                <label style={{ fontSize: "11px", color: "#666" }}>
                  Column Mapping
                </label>
                <div className="margin-small" style={{ marginTop: "4px" }}>
                  <input
                    value={manyToMany?.left_column ?? ""}
                    onChange={(e) =>
                      props.onEventUpdateManyToManyConfig(
                        props.nodeId,
                        props.currentRowIndex,
                        "left_column",
                        e.target.value
                      )
                    }
                    placeholder="left_column (e.g. option_id)"
                  />
                </div>
                <div className="margin-small">
                  <input
                    value={manyToMany?.right_column ?? ""}
                    onChange={(e) =>
                      props.onEventUpdateManyToManyConfig(
                        props.nodeId,
                        props.currentRowIndex,
                        "right_column",
                        e.target.value
                      )
                    }
                    placeholder="right_column (e.g. technology_id)"
                  />
                </div>
              </div>

              <div style={{ marginTop: "8px", width: "100%" }}>
                <CheckBox
                  label="Self-referential relationship"
                  checked={manyToMany?.self_referential ?? false}
                  onEventToggle={() =>
                    props.onEventUpdateManyToManyConfig(
                      props.nodeId,
                      props.currentRowIndex,
                      "self_referential",
                      !(manyToMany?.self_referential ?? false)
                    )
                  }
                />
                {manyToMany?.self_referential && (
                  <div
                    style={{
                      marginTop: "8px",
                      padding: "8px",
                      backgroundColor: "#e3f2fd",
                      borderRadius: "4px",
                    }}
                  >
                    <div className="margin-small">
                      <input
                        value={manyToMany?.primaryjoin ?? ""}
                        onChange={(e) =>
                          props.onEventUpdateManyToManyConfig(
                            props.nodeId,
                            props.currentRowIndex,
                            "primaryjoin",
                            e.target.value
                          )
                        }
                        placeholder="primaryjoin (e.g. Option.id == Table.option_id)"
                      />
                    </div>
                    <div className="margin-small">
                      <input
                        value={manyToMany?.secondaryjoin ?? ""}
                        onChange={(e) =>
                          props.onEventUpdateManyToManyConfig(
                            props.nodeId,
                            props.currentRowIndex,
                            "secondaryjoin",
                            e.target.value
                          )
                        }
                        placeholder="secondaryjoin (e.g. Option.id == Table.avoided_id)"
                      />
                    </div>
                  </div>
                )}
              </div>

              <div
                style={{
                  marginTop: "12px",
                  padding: "8px",
                  backgroundColor: "#f5f5f5",
                  borderRadius: "4px",
                  width: "100%",
                }}
              ></div>
            </div>
          )}
        </>
      )}
    </DesignNotes>
  );
}
