import * as React from "react";
import ReactFlow, {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  Background,
  Controls,
  MiniMap,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
} from "react-flow-renderer";
import NavbarComponent from "./Navbar";
import ORMDiagram from "./ORMDiagram";
import {
  ORMNodeData,
  ORMKeyBehavior,
  ORMRow,
  ORMManyToManyConfig,
  ORMLinkedProperty,
} from "./ORMDiagram";

// ======================= //
//                         //
//   TYPE DEFINITIONS      //
//                         //
// ======================= //

const nodeTypes = { ormDiagram: ORMDiagram };

type RowField = "required" | "name" | "type";

// ======================= //
//                         //
//   UTILITY METHODS       //
//                         //
// ======================= //

const getRandomNumber = (maxNum: number) => {
  return Math.floor(Math.random() * maxNum);
};

const getRandomColor = () => {
  const r = getRandomNumber(200);
  const g = getRandomNumber(200);
  const b = getRandomNumber(200);

  return `rgb(${r}, ${g}, ${b})`;
};

const initialEdges: Edge[] = [];

const initialNodes: Node<ORMNodeData>[] = [
  {
    id: "node-EntityName",
    type: "ormDiagram",
    position: { x: 500, y: 500 },
    data: {
      name: "EntityName",
      table_name: "table_name",
      color: getRandomColor(),
      description: "Entity description",
      properties: [
        {
          name: "id",
          type: "int",
          description: "Primary key",
          required: true,
          key_type: {
            type: "primary_key",
            behaviors: ["auto_increment"],
          },
        },
      ],
      currentRowIndex: 0,
      modalMode: null,
      unique_constraints: [],
    },
  },
];

const getDataFromBackend = (callBack: (data: any) => void, endpoint: string) => {
  fetch(`http://localhost:8000/${endpoint}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  })
    .then((res) => res.json())
    .then((data) => {
      callBack(data);
    })
    .catch((err) => {
      console.error("Error fetching from backend:", err);
      alert("Error fetching from backend.");
    });
};

const postDataToBackend = (data: any, endpoint: string) => {
  fetch(`http://localhost:8000/${endpoint}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  })
    .then((res) => res.json())
    .then((data) => {
      console.log("Successfully posted to backend:", data);
    })
    .catch((err) => {
      console.error("Error posting to backend:", err);
    });
};

// ======================= //
//                         //
//   MAIN COMPONENT        //
//                         //
// ======================= //

export default function App() {
  // ====================== //
  //                        //
  //   STATE VARIABLES      //
  //                        //
  // ====================== //

  const [edges, setEdges] = React.useState<Edge[]>(initialEdges);
  const [nodes, setNodes] = React.useState<Node<ORMNodeData>[]>(initialNodes);
  const [version, setVersion] = React.useState<string>("1.0.0");

  // ================= //
  //                   //
  //   SIDE EFFECTS    //
  //                   //
  // ================= //

  React.useEffect(() => {
    if (nodes.length === 0 && edges.length === 0) {
      return;
    }
    if (nodes === initialNodes && edges === initialEdges) {
      return;
    }
    handleSaveToBackend();
  }, [nodes, edges]);

  React.useEffect(() => {
    getDataFromBackend((data) => {
      setNodes(data.nodes);
      setEdges(data.edges);
    }, "dao");

    getDataFromBackend((data) => {
      setVersion(data.version);
    }, "version");
  }, []);

  // ====================== //
  //                        //
  //   OBSERVE STATE        //
  //                        //
  // ====================== //

  console.log("nodes", nodes);
  console.log("edges", edges);

  // ====================== //
  //                        //
  //   UI EVENT HANDLERS    //
  //                        //
  // ====================== //

  // ------------------------------------------------------ Save
  const handleSaveToBackend = () => {
    postDataToBackend({ nodes, edges }, "dao");
  };

  // ------------------------------------------------------ Node
  const handleEventNodesChange = React.useCallback(
    (changes: NodeChange[]) =>
      setNodes((prevNodes) => applyNodeChanges(changes, prevNodes)),
    []
  );

  const handleEventEdgesChange = React.useCallback(
    (changes: EdgeChange[]) =>
      setEdges((prevEdges) => applyEdgeChanges(changes, prevEdges)),
    []
  );

  const getRowIndexFromHandle = (handleId?: string | null) => {
    if (!handleId) {
      return null;
    }
    const [, indexValue] = handleId.split("-");
    const index = Number(indexValue);
    return Number.isNaN(index) ? null : index;
  };

  const handleEventConnect = React.useCallback((connection: Connection) => {
    setEdges((prevEdges) => addEdge(connection, prevEdges));
    if (!connection.source || !connection.target) {
      return;
    }
    const sourceIndex = getRowIndexFromHandle(connection.sourceHandle);
    const targetIndex = getRowIndexFromHandle(connection.targetHandle);
    if (sourceIndex === null || targetIndex === null) {
      return;
    }

    setNodes((prevNodes) => {
      const sourceNode = prevNodes.find((node) => node.id === connection.source);
      const targetNode = prevNodes.find((node) => node.id === connection.target);
      if (!sourceNode || !targetNode) {
        return prevNodes;
      }

      const sourceRow = sourceNode.data.properties[sourceIndex];
      const targetRow = targetNode.data.properties[targetIndex];
      if (!sourceRow || !targetRow) {
        return prevNodes;
      }

      return prevNodes.map((node) => {
        if (node.id !== sourceNode.id && node.id !== targetNode.id) {
          return node;
        }

        const isSourceNode = node.id === sourceNode.id;
        const linkedProperty = isSourceNode
          ? { table: targetNode.data.name, property: targetRow.name }
          : { table: sourceNode.data.name, property: sourceRow.name };
        const rowIndex = isSourceNode ? sourceIndex : targetIndex;

        return {
          ...node,
          data: {
            ...node.data,
            properties: node.data.properties.map((row, index) =>
              index !== rowIndex ? row : { ...row, linked_property: linkedProperty }
            ),
          },
        };
      });
    });
  }, []);

  const updateNodeData = React.useCallback(
    (nodeId: string, update: (data: ORMNodeData) => ORMNodeData) => {
      setNodes((prevNodes) =>
        prevNodes.map((node) =>
          node.id !== nodeId
            ? node
            : {
                ...node,
                data: update(node.data),
              }
        )
      );
    },
    []
  );

  // ------------------------------------------------------ Diagram

  const handleEventCreateTable = () => {
    setNodes((prevNodes) => {
      const nextNode: Node<ORMNodeData> = {
        id: crypto.randomUUID(),
        type: "ormDiagram",
        position: { x: 10, y: 10 },
        data: {
          name: "EntityName",
          table_name: "entities",
          description: "Entity description",
          color: getRandomColor(),
          properties: [createDefaultPrimaryKeyRow(), createDefaultRow()],
          currentRowIndex: 0,
          modalMode: null,
        },
      };
      return [...prevNodes, nextNode];
    });
  };

  const handleEventUpdateObjectName = (nodeId: string, name: string) => {
    updateNodeData(nodeId, (data) => ({
      ...data,
      name,
    }));
  };

  const handleEventUpdateTableName = (nodeId: string, tableName: string) => {
    updateNodeData(nodeId, (data) => ({
      ...data,
      table_name: tableName,
    }));
  };

  const handleEventUpdateObjectComment = (nodeId: string, description: string) => {
    updateNodeData(nodeId, (data) => ({
      ...data,
      description,
    }));
  };

  // ------------------------------------------------------ Modal Diagram

  const handleEventToggleRowModal = (nodeId: string, rowIndex: number) => {
    updateNodeData(nodeId, (data) => ({
      ...data,
      currentRowIndex: rowIndex,
      modalMode:
        data.modalMode === "row" && data.currentRowIndex === rowIndex ? null : "row",
    }));
  };

  const handleEventToggleTableModal = (nodeId: string) => {
    updateNodeData(nodeId, (data) => ({
      ...data,
      modalMode: data.modalMode === "table" ? null : "table",
    }));
  };

  const handleEventToggleAssociationTable = (nodeId: string) => {
    updateNodeData(nodeId, (data) => ({
      ...data,
      is_association_table: !data.is_association_table,
    }));
  };

  const handleEventAddUniqueConstraint = (nodeId: string) => {
    updateNodeData(nodeId, (data) => ({
      ...data,
      unique_constraints: [...(data.unique_constraints || []), []],
    }));
  };

  const handleEventRemoveUniqueConstraint = (
    nodeId: string,
    constraintIndex: number
  ) => {
    updateNodeData(nodeId, (data) => ({
      ...data,
      unique_constraints: (data.unique_constraints || []).filter(
        (_, index) => index !== constraintIndex
      ),
    }));
  };

  const handleEventUpdateUniqueConstraint = (
    nodeId: string,
    constraintIndex: number,
    value: string
  ) => {
    updateNodeData(nodeId, (data) => {
      const constraints = [...(data.unique_constraints || [])];
      constraints[constraintIndex] = value
        .split(",")
        .map((col) => col.trim())
        .filter((col) => col.length > 0);
      return {
        ...data,
        unique_constraints: constraints,
      };
    });
  };

  // ------------------------------------------------------ Row Diagram

  const handleEventAddRow = (nodeId: string) => {
    updateNodeData(nodeId, (data) => ({
      ...data,
      properties: [...data.properties, createDefaultRow()],
    }));
  };

  const handleEventUpdateRowField = (
    nodeId: string,
    rowIndex: number,
    field: RowField,
    value: string
  ) => {
    updateNodeData(nodeId, (data) => ({
      ...data,
      properties: data.properties.map((row, index) => {
        if (index !== rowIndex) {
          return row;
        }
        if (field === "required") {
          return { ...row, required: value === "required" };
        }
        return { ...row, [field]: value };
      }),
    }));
  };

  const handleEventUpdateRowDescription = (
    nodeId: string,
    rowIndex: number,
    description: string
  ) => {
    updateNodeData(nodeId, (data) => ({
      ...data,
      properties: data.properties.map((row, index) =>
        index !== rowIndex ? row : { ...row, description }
      ),
    }));
  };

  const handleEventUpdateRowKeyType = (
    nodeId: string,
    rowIndex: number,
    keyType: "none" | "primary_key" | "foreign_key"
  ) => {
    updateNodeData(nodeId, (data) => ({
      ...data,
      properties: data.properties.map((row, index) => {
        if (index !== rowIndex) {
          return row;
        }
        if (keyType === "none") {
          return {
            ...row,
            key_type: undefined,
            linked_property: undefined,
          };
        }
        if (keyType === "primary_key") {
          const behaviors = row.key_type?.behaviors ?? [];
          return {
            ...row,
            linked_property: undefined,
            key_type: {
              type: "primary_key",
              behaviors,
            },
          };
        }
        const behaviors = row.key_type?.behaviors ?? [];
        return {
          ...row,
          key_type: {
            type: keyType,
            behaviors,
            table: row.key_type?.table ?? row.linked_property?.table ?? "",
            column: row.key_type?.column ?? row.linked_property?.property ?? "",
          },
        };
      }),
    }));
  };

  const handleEventToggleRowBehavior = (
    nodeId: string,
    rowIndex: number,
    behavior: ORMKeyBehavior
  ) => {
    updateNodeData(nodeId, (data) => ({
      ...data,
      properties: data.properties.map((row, index) => {
        if (index !== rowIndex || !row.key_type) {
          return row;
        }
        const behaviors = row.key_type.behaviors.includes(behavior)
          ? row.key_type.behaviors.filter((item) => item !== behavior)
          : [...row.key_type.behaviors, behavior];
        return {
          ...row,
          key_type: {
            ...row.key_type,
            behaviors,
          },
        };
      }),
    }));
  };

  const handleEventUpdateManyToManyConfig = (
    nodeId: string,
    rowIndex: number,
    field: keyof ORMManyToManyConfig,
    value: string | boolean
  ) => {
    updateNodeData(nodeId, (data) => ({
      ...data,
      properties: data.properties.map((row, index) => {
        if (index !== rowIndex) {
          return row;
        }
        const currentM2M = row.many_to_many ?? {
          association_table: "",
          self_referential: false,
        };
        return {
          ...row,
          many_to_many: {
            ...currentM2M,
            [field]: value,
          },
        };
      }),
    }));
  };

  const handleEventUpdateRowDefaultValue = (
    nodeId: string,
    rowIndex: number,
    defaultValue: string
  ) => {
    updateNodeData(nodeId, (data) => ({
      ...data,
      properties: data.properties.map((row, index) =>
        index !== rowIndex
          ? row
          : { ...row, default_value: defaultValue || undefined }
      ),
    }));
  };

  const handleEventUpdateRowEnumName = (
    nodeId: string,
    rowIndex: number,
    enumName: string
  ) => {
    updateNodeData(nodeId, (data) => ({
      ...data,
      properties: data.properties.map((row, index) =>
        index !== rowIndex ? row : { ...row, enum_name: enumName || undefined }
      ),
    }));
  };

  const handleEventUpdateLinkedPropertyField = (
    nodeId: string,
    rowIndex: number,
    field: keyof ORMLinkedProperty,
    value: string
  ) => {
    updateNodeData(nodeId, (data) => ({
      ...data,
      properties: data.properties.map((row, index) => {
        if (index !== rowIndex || !row.linked_property) {
          return row;
        }
        return {
          ...row,
          linked_property: {
            ...row.linked_property,
            [field]: value || undefined,
          },
        };
      }),
    }));
  };

  const handleEventDeleteRow = (nodeId: string) => {
    let shouldDeleteNode = false;
    setNodes((prevNodes) =>
      prevNodes.reduce<Node<ORMNodeData>[]>((acc, node) => {
        if (node.id !== nodeId) {
          acc.push(node);
          return acc;
        }
        if (node.data.properties.length <= 1) {
          shouldDeleteNode = true;
          return acc;
        }
        acc.push({
          ...node,
          data: {
            ...node.data,
            properties: node.data.properties.slice(
              0,
              node.data.properties.length - 1
            ),
          },
        });
        return acc;
      }, [])
    );
    if (shouldDeleteNode) {
      setEdges((prevEdges) =>
        prevEdges.filter((edge) => edge.source !== nodeId && edge.target !== nodeId)
      );
    }
  };

  // ====================== //
  //                        //
  //   UTILS METHODS        //
  //                        //
  // ====================== //

  const createDefaultRow = (): ORMRow => ({
    name: "name",
    type: "str",
    description: "The name of the ORM Object",
    required: true,
  });

  const createDefaultPrimaryKeyRow = (): ORMRow => ({
    name: "id",
    type: "int",
    description: "Unique identifier for the row",
    required: true,
    key_type: {
      type: "primary_key",
      behaviors: ["auto_increment"],
    },
  });

  const nodesWithHandlers = React.useMemo<Node<ORMNodeData>[]>(() => {
    const allNodesSummary = nodes.map((n) => ({
      id: n.id,
      name: n.data.name,
      table_name: n.data.table_name,
    }));

    return nodes.map((node) => ({
      ...node,
      data: {
        ...node.data,
        onEventAddRow: handleEventAddRow,
        onEventDeleteRow: handleEventDeleteRow,
        onEventToggleRowModal: handleEventToggleRowModal,
        onEventToggleTableModal: handleEventToggleTableModal,
        onEventUpdateObjectName: handleEventUpdateObjectName,
        onEventUpdateObjectComment: handleEventUpdateObjectComment,
        onEventUpdateTableName: handleEventUpdateTableName,
        onEventUpdateRowField: handleEventUpdateRowField,
        onEventUpdateRowDescription: handleEventUpdateRowDescription,
        onEventUpdateRowKeyType: handleEventUpdateRowKeyType,
        onEventToggleRowBehavior: handleEventToggleRowBehavior,
        onEventUpdateManyToManyConfig: handleEventUpdateManyToManyConfig,
        onEventUpdateRowDefaultValue: handleEventUpdateRowDefaultValue,
        onEventUpdateRowEnumName: handleEventUpdateRowEnumName,
        onEventUpdateLinkedPropertyField: handleEventUpdateLinkedPropertyField,
        onEventCreateTable: handleEventCreateTable,
        onEventToggleAssociationTable: handleEventToggleAssociationTable,
        onEventAddUniqueConstraint: handleEventAddUniqueConstraint,
        onEventRemoveUniqueConstraint: handleEventRemoveUniqueConstraint,
        onEventUpdateUniqueConstraint: handleEventUpdateUniqueConstraint,
        allNodes: allNodesSummary,
      },
    }));
  }, [
    nodes,
    handleEventAddRow,
    handleEventDeleteRow,
    handleEventToggleRowModal,
    handleEventToggleTableModal,
    handleEventUpdateObjectComment,
    handleEventUpdateObjectName,
    handleEventUpdateTableName,
    handleEventUpdateRowField,
    handleEventUpdateRowDescription,
    handleEventUpdateRowKeyType,
    handleEventToggleRowBehavior,
    handleEventUpdateManyToManyConfig,
    handleEventUpdateRowDefaultValue,
    handleEventUpdateRowEnumName,
    handleEventUpdateLinkedPropertyField,
    handleEventCreateTable,
    handleEventToggleAssociationTable,
    handleEventAddUniqueConstraint,
    handleEventRemoveUniqueConstraint,
    handleEventUpdateUniqueConstraint,
  ]);

  // ====================== //
  //                        //
  //   UI COMPONENTS        //
  //                        //
  // ====================== //

  return (
    <div>
      {/* Top bar */}
      <section style={{ margin: "0% 20%" }}>
        <NavbarComponent
          version={version}
          onEventCreateTable={handleEventCreateTable}
        />
      </section>

      {/* Main layout */}
      <section style={{ margin: "0% 2%" }}>
        <div className="functions-list"></div>
        <div className="data-model-canvas">
          <div style={{ width: "100%", height: "85vh" }}>
            <ReactFlow
              nodes={nodesWithHandlers}
              edges={edges}
              onNodesChange={handleEventNodesChange}
              onEdgesChange={handleEventEdgesChange}
              onConnect={handleEventConnect}
              nodeTypes={nodeTypes}
            >
              <Background />
              <Controls />
              <MiniMap />
            </ReactFlow>
          </div>
        </div>
      </section>
    </div>
  );
}
