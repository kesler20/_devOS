from __future__ import annotations
import hashlib
import logging
import re
import typing
import pydantic
from devOS.domain import entities
from devOS.use_cases.utils.file_io import File

logger = logging.getLogger(__name__)


# ============================== #
#                                #
#   ReactFlow output structures  #
#                                #
# ============================== #


class ReactFlowORMKeyType(pydantic.BaseModel):
    type: typing.Literal["primary_key", "foreign_key"]
    behaviors: list[str]
    table: typing.Optional[str] = None
    column: typing.Optional[str] = None

    model_config = pydantic.ConfigDict(extra="ignore")


class ReactFlowORMLinkedProperty(pydantic.BaseModel):
    table: str
    property: str
    cascade: typing.Optional[str] = None
    order_by: typing.Optional[str] = None
    foreign_key: typing.Optional[str] = None

    model_config = pydantic.ConfigDict(extra="ignore")


class ReactFlowORMManyToManyConfig(pydantic.BaseModel):
    association_table: str
    self_referential: bool = False
    left_column: typing.Optional[str] = None
    right_column: typing.Optional[str] = None
    primaryjoin: typing.Optional[str] = None
    secondaryjoin: typing.Optional[str] = None

    model_config = pydantic.ConfigDict(extra="ignore")


class ReactFlowORMRow(pydantic.BaseModel):
    name: str
    type: str
    description: str
    required: bool
    default_value: typing.Optional[str] = None
    enum_name: typing.Optional[str] = None
    key_type: typing.Optional[ReactFlowORMKeyType] = None
    linked_property: typing.Optional[ReactFlowORMLinkedProperty] = None
    many_to_many: typing.Optional[ReactFlowORMManyToManyConfig] = None

    model_config = pydantic.ConfigDict(extra="ignore")


class ReactFlowORMNodeData(pydantic.BaseModel):
    name: str
    table_name: str
    description: str
    color: str
    properties: list[ReactFlowORMRow]
    currentRowIndex: int
    modalMode: typing.Optional[typing.Literal["table", "row"]] = None
    is_association_table: bool = False
    unique_constraints: typing.Optional[list[list[str]]] = None

    model_config = pydantic.ConfigDict(extra="ignore")


class ReactFlowPosition(pydantic.BaseModel):
    x: float
    y: float


class ReactFlowNode(pydantic.BaseModel):
    id: str
    type: str
    position: ReactFlowPosition
    data: ReactFlowORMNodeData
    width: int
    height: int
    positionAbsolute: typing.Optional[ReactFlowPosition] = None
    selected: typing.Optional[bool] = None
    dragging: typing.Optional[bool] = None

    model_config = pydantic.ConfigDict(extra="ignore")


class ReactFlowEdge(pydantic.BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: str
    targetHandle: str

    model_config = pydantic.ConfigDict(extra="ignore")


# =================== #
#                     #
#   Public API        #
#                     #
# =================== #


def convert_dao_spec_to_reactflow(
    dao_spec: list[dict[str, typing.Any]] | list[entities.DAOSchemaSpec],
    *,
    include_foreign_key_edges: bool = False,
    saved_positions: typing.Optional[dict[str, dict[str, float]]] = None,
) -> tuple[list[dict[str, typing.Any]], list[dict[str, typing.Any]]]:
    """
    Convert a DAO spec (list of DAOSchemaSpec) into its ReactFlow representation
    (nodes, edges).

    Edges are primarily generated from `linked_property` pairs. If both sides of a
    relationship define linked_property, the relationship is de-duplicated into a
    single edge.

    Parameters
    ----------
    dao_spec
        DAO schema specs as dicts or validated DAOSchemaSpec objects.
    include_foreign_key_edges
        If True, also create edges from each foreign-key property to the referenced
        table's primary key property (when resolvable). This is optional and can
        be noisy, depending on your UI preferences.
    saved_positions
        Optional dictionary mapping node IDs to their saved positions.
        Format: {"node-EntityName": {"x": 100.0, "y": 200.0}, ...}

    Returns
    -------
    (nodes, edges)
        ReactFlow-ready nodes and edges as plain dictionaries.
    """
    specs = [_validate_spec(s) for s in dao_spec]

    converter = _DaoSpecToReactFlowConverter(
        include_foreign_key_edges=include_foreign_key_edges,
        saved_positions=saved_positions or {},
    )
    nodes, edges = converter.convert(specs)

    node_dicts = [n.model_dump() for n in nodes]
    edge_dicts = [e.model_dump() for e in edges]
    return node_dicts, edge_dicts


# ============================== #
#                                #
#   Internal converter           #
#                                #
# ============================== #


class _DaoSpecToReactFlowConverter:
    def __init__(
        self,
        *,
        include_foreign_key_edges: bool,
        saved_positions: dict[str, dict[str, float]],
    ) -> None:
        self._include_foreign_key_edges = include_foreign_key_edges
        self._saved_positions = saved_positions

    def _get_position(self, node_id: str, fallback_index: int) -> ReactFlowPosition:
        """Get saved position for a node, or generate a default position."""
        if node_id in self._saved_positions:
            pos = self._saved_positions[node_id]
            return ReactFlowPosition(x=pos.get("x", 0.0), y=pos.get("y", 0.0))
        return _default_position(fallback_index)

    def convert(
        self,
        specs: list[entities.DAOSchemaSpec],
    ) -> tuple[list[ReactFlowNode], list[ReactFlowEdge]]:
        # Use entity name as stable node ID to avoid conflicts on delete/recreate
        node_ids_by_class_name = {spec.name: f"node-{spec.name}" for spec in specs}
        specs_by_class_name = {spec.name: spec for spec in specs}
        specs_by_table_name = {spec.table_name: spec for spec in specs}

        nodes: list[ReactFlowNode] = []
        assoc_table_node_ids: dict[str, str] = {}
        node_count = 0

        for i, spec in enumerate(specs):
            node_id = node_ids_by_class_name[spec.name]
            position = self._get_position(node_id, node_count)
            node = self._make_node(node_id=node_id, spec=spec, position=position)
            nodes.append(node)
            node_count += 1

        print("Creating association table nodes...")
        for spec in specs:
            if not spec.association_tables:
                continue
            for assoc_table in spec.association_tables:
                class_name = assoc_table.class_name or _convert_to_pascal(
                    assoc_table.table_name
                )
                if class_name in node_ids_by_class_name:
                    continue
                if assoc_table.table_name in assoc_table_node_ids:
                    continue

                node_id = f"node-{class_name}"
                assoc_table_node_ids[assoc_table.table_name] = node_id
                node_ids_by_class_name[class_name] = node_id

                position = self._get_position(node_id, node_count)
                assoc_node = self._make_association_table_node(
                    node_id=node_id,
                    assoc_table=assoc_table,
                    position=position,
                )
                nodes.append(assoc_node)
                node_count += 1
                print(
                    f"  Created association table node: {class_name} ({assoc_table.table_name})"
                )

        property_index = _build_property_index(nodes)

        edges: list[ReactFlowEdge] = []
        edges_by_key: dict[tuple[str, int, str, int], ReactFlowEdge] = {}

        print("Creating edges from linked_property relationships...")
        for spec in specs:
            for prop in spec.properties:
                if prop.linked_property is None:
                    continue

                left_class_name = spec.name
                left_prop_name = prop.name
                right_class_name = prop.linked_property.table
                right_prop_name = prop.linked_property.property

                if right_class_name not in specs_by_class_name:
                    logger.warning(
                        "Skipping linked_property: target table not found in dao_spec: %s.%s -> %s.%s",
                        left_class_name,
                        left_prop_name,
                        right_class_name,
                        right_prop_name,
                    )
                    continue

                left_node_id = node_ids_by_class_name[left_class_name]
                right_node_id = node_ids_by_class_name[right_class_name]

                left_index = property_index.get((left_node_id, left_prop_name))
                if left_index is None:
                    logger.debug(
                        "Skipping linked_property edge: left property not found: %s.%s",
                        left_class_name,
                        left_prop_name,
                    )
                    continue

                right_index = property_index.get((right_node_id, right_prop_name))
                if right_index is None:
                    logger.debug(
                        "Skipping linked_property edge: right property not found: %s.%s",
                        right_class_name,
                        right_prop_name,
                    )
                    continue

                # Deduplicate bidirectional linked_property pairs using a canonical key
                a = (left_node_id, left_index)
                b = (right_node_id, right_index)
                (n1, i1), (n2, i2) = sorted([a, b])
                canonical_key = (n1, i1, n2, i2)
                if canonical_key in edges_by_key:
                    continue

                # Determine source/target based on relationship semantics:
                # - The "array" side (parent with many children) should be the source
                # - The "object" side (child referencing parent) should be the target
                # Look up the other side's property to compare types
                right_spec = specs_by_class_name[right_class_name]
                right_prop = _find_property_by_name(right_spec, right_prop_name)

                left_type = (prop.type or "").lower()
                right_type = (right_prop.type if right_prop else "").lower()

                # array -> object (parent to child)
                if left_type == "array" and right_type == "object":
                    source_node_id, source_idx = left_node_id, left_index
                    target_node_id, target_idx = right_node_id, right_index
                elif left_type == "object" and right_type == "array":
                    source_node_id, source_idx = right_node_id, right_index
                    target_node_id, target_idx = left_node_id, left_index
                else:
                    # Fallback: array is source, otherwise left is source
                    if left_type == "array":
                        source_node_id, source_idx = left_node_id, left_index
                        target_node_id, target_idx = right_node_id, right_index
                    else:
                        source_node_id, source_idx = right_node_id, right_index
                        target_node_id, target_idx = left_node_id, left_index

                source_handle = f"row-{source_idx}"
                target_handle = f"row-{target_idx}"
                edge_id = _edge_id(
                    source_node_id, source_handle, target_node_id, target_handle
                )

                edge = ReactFlowEdge(
                    id=edge_id,
                    source=source_node_id,
                    sourceHandle=source_handle,
                    target=target_node_id,
                    targetHandle=target_handle,
                )
                edges_by_key[canonical_key] = edge
                edges.append(edge)

        print("Creating edges from association tables to referenced entities...")
        assoc_edges = self._make_association_table_edges(
            specs=specs,
            nodes=nodes,
            node_ids_by_class_name=node_ids_by_class_name,
            specs_by_table_name=specs_by_table_name,
            property_index=property_index,
            assoc_table_node_ids=assoc_table_node_ids,
        )
        for edge in assoc_edges:
            key = _edge_key(edge)
            if key in edges_by_key:
                continue
            edges_by_key[key] = edge
            edges.append(edge)

        if self._include_foreign_key_edges:
            print("Creating additional edges from foreign keys to primary keys...")
            fk_edges = self._make_foreign_key_edges(
                specs=specs,
                node_ids_by_class_name=node_ids_by_class_name,
                specs_by_table_name=specs_by_table_name,
                property_index=property_index,
            )
            for edge in fk_edges:
                key = _edge_key(edge)
                if key in edges_by_key:
                    continue
                edges_by_key[key] = edge
                edges.append(edge)

        return nodes, edges

    def _make_association_table_edges(
        self,
        *,
        specs: list[entities.DAOSchemaSpec],
        nodes: list[ReactFlowNode],
        node_ids_by_class_name: dict[str, str],
        specs_by_table_name: dict[str, entities.DAOSchemaSpec],
        property_index: dict[tuple[str, str], int],
        assoc_table_node_ids: dict[str, str],
    ) -> list[ReactFlowEdge]:
        """Create edges from association table FK columns to referenced entity PKs."""
        edges: list[ReactFlowEdge] = []

        for spec in specs:
            if not spec.association_tables:
                continue

            for assoc_table in spec.association_tables:
                assoc_node_id = assoc_table_node_ids.get(assoc_table.table_name)
                if not assoc_node_id:
                    continue

                assoc_node = next((n for n in nodes if n.id == assoc_node_id), None)
                if not assoc_node:
                    continue

                for col_idx, col in enumerate(assoc_table.columns):
                    referenced_spec = specs_by_table_name.get(col.foreign_key_table)
                    if not referenced_spec:
                        logger.warning(
                            "Association table %s references unknown table: %s",
                            assoc_table.table_name,
                            col.foreign_key_table,
                        )
                        continue

                    referenced_node_id = node_ids_by_class_name.get(
                        referenced_spec.name
                    )
                    if not referenced_node_id:
                        continue

                    pk_prop = _find_primary_key_property(referenced_spec)
                    pk_idx = property_index.get((referenced_node_id, pk_prop.name))
                    if pk_idx is None:
                        continue

                    source_handle = f"row-{col_idx}"
                    target_handle = f"row-{pk_idx}"
                    edge_id = _edge_id(
                        assoc_node_id, source_handle, referenced_node_id, target_handle
                    )

                    edge = ReactFlowEdge(
                        id=edge_id,
                        source=assoc_node_id,
                        sourceHandle=source_handle,
                        target=referenced_node_id,
                        targetHandle=target_handle,
                    )
                    edges.append(edge)
                    print(
                        f"  Created edge: {assoc_table.table_name}.{col.name} -> "
                        f"{referenced_spec.name}.{pk_prop.name}"
                    )

        return edges

    def _make_node(
        self, *, node_id: str, spec: entities.DAOSchemaSpec, position: ReactFlowPosition
    ) -> ReactFlowNode:
        color = _stable_color(spec.name)
        rows = [self._make_row(p) for p in spec.properties]

        data = ReactFlowORMNodeData(
            name=spec.name,
            table_name=spec.table_name,
            description=spec.description or "",
            color=color,
            properties=rows,
            currentRowIndex=0,
            modalMode=None,
            is_association_table=False,
            unique_constraints=spec.unique_constraints or [],
        )

        width = 600
        height = _node_height(len(rows))

        node = ReactFlowNode(
            id=node_id,
            type="ormDiagram",
            position=position,
            positionAbsolute=position,
            data=data,
            width=width,
            height=height,
            selected=False,
            dragging=False,
        )
        return node

    def _make_association_table_node(
        self,
        *,
        node_id: str,
        assoc_table: entities.DAOSchemaAssociationTable,
        position: ReactFlowPosition,
    ) -> ReactFlowNode:
        """Create a ReactFlow node for an association table."""
        color = _stable_color(assoc_table.table_name)
        class_name = assoc_table.class_name or _convert_to_pascal(
            assoc_table.table_name
        )

        rows: list[ReactFlowORMRow] = []
        for col in assoc_table.columns:
            behaviors: list[str] = []
            if col.ondelete:
                behaviors.append(f"ondelete_{col.ondelete.lower()}")

            key_type = ReactFlowORMKeyType(
                type="foreign_key",
                behaviors=behaviors,
                table=col.foreign_key_table,
                column=col.foreign_key_column,
            )

            row = ReactFlowORMRow(
                name=col.name,
                type=col.type,
                description=f"Foreign key to {col.foreign_key_table}.{col.foreign_key_column}",
                required=True,
                key_type=key_type,
                linked_property=None,
                many_to_many=None,
            )
            rows.append(row)

        if assoc_table.extra_properties:
            for prop in assoc_table.extra_properties:
                rows.append(self._make_row(prop))

        data = ReactFlowORMNodeData(
            name=class_name,
            table_name=assoc_table.table_name,
            description=f"Association table for many-to-many relationship",
            color=color,
            properties=rows,
            currentRowIndex=0,
            modalMode=None,
            is_association_table=True,
            unique_constraints=assoc_table.unique_constraints or [],
        )

        width = 600
        height = _node_height(len(rows))

        return ReactFlowNode(
            id=node_id,
            type="ormDiagram",
            position=position,
            positionAbsolute=position,
            data=data,
            width=width,
            height=height,
            selected=False,
            dragging=False,
        )

    def _make_row(self, prop: entities.DAOSchemaProperty) -> ReactFlowORMRow:
        key_type = None
        if prop.key_type is not None:
            behaviors = list(prop.key_type.behaviors or [])
            key_type = ReactFlowORMKeyType(
                type=typing.cast(
                    typing.Literal["primary_key", "foreign_key"], prop.key_type.type
                ),
                behaviors=behaviors,
                table=prop.key_type.table,
                column=prop.key_type.column,
            )

        linked_property = None
        if prop.linked_property is not None:
            linked_property = ReactFlowORMLinkedProperty(
                table=prop.linked_property.table,
                property=prop.linked_property.property,
                cascade=prop.linked_property.cascade,
                order_by=prop.linked_property.order_by,
                foreign_key=prop.linked_property.foreign_key,
            )

        many_to_many = None
        if prop.many_to_many is not None:
            many_to_many = ReactFlowORMManyToManyConfig(
                association_table=prop.many_to_many.association_table,
                self_referential=prop.many_to_many.self_referential,
                left_column=prop.many_to_many.left_column,
                right_column=prop.many_to_many.right_column,
                primaryjoin=prop.many_to_many.primaryjoin,
                secondaryjoin=prop.many_to_many.secondaryjoin,
            )

        return ReactFlowORMRow(
            name=prop.name,
            type=prop.type,
            description=prop.description or "",
            required=bool(prop.required) if prop.required is not None else False,
            default_value=prop.default_value,
            enum_name=prop.enum_name,
            key_type=key_type,
            linked_property=linked_property,
            many_to_many=many_to_many,
        )

    def _make_foreign_key_edges(
        self,
        *,
        specs: list[entities.DAOSchemaSpec],
        node_ids_by_class_name: dict[str, str],
        specs_by_table_name: dict[str, entities.DAOSchemaSpec],
        property_index: dict[tuple[str, str], int],
    ) -> list[ReactFlowEdge]:
        edges: list[ReactFlowEdge] = []

        for spec in specs:
            for prop in spec.properties:
                if prop.key_type is None or prop.key_type.type != "foreign_key":
                    continue
                if not prop.key_type.table:
                    continue

                referenced_spec = specs_by_table_name.get(prop.key_type.table)
                if referenced_spec is None:
                    logger.warning(
                        "Skipping foreign key edge: referenced table not found: %s.%s -> %s",
                        spec.name,
                        prop.name,
                        prop.key_type.table,
                    )
                    continue

                fk_owner_node_id = node_ids_by_class_name[spec.name]
                fk_idx = property_index.get((fk_owner_node_id, prop.name))
                if fk_idx is None:
                    continue

                pk_prop = _find_primary_key_property(referenced_spec)
                referenced_node_id = node_ids_by_class_name[referenced_spec.name]
                pk_idx = property_index.get((referenced_node_id, pk_prop.name))
                if pk_idx is None:
                    continue

                a = (fk_owner_node_id, fk_idx)
                b = (referenced_node_id, pk_idx)
                (source_node_id, source_idx), (target_node_id, target_idx) = sorted(
                    [a, b]
                )

                source_handle = f"row-{source_idx}"
                target_handle = f"row-{target_idx}"
                edge_id = _edge_id(
                    source_node_id, source_handle, target_node_id, target_handle
                )

                edges.append(
                    ReactFlowEdge(
                        id=edge_id,
                        source=source_node_id,
                        sourceHandle=source_handle,
                        target=target_node_id,
                        targetHandle=target_handle,
                    )
                )

        return edges


# ============================== #
#                                #
#   Helpers                      #
#                                #
# ============================== #


def _validate_spec(
    spec: dict[str, typing.Any] | entities.DAOSchemaSpec
) -> entities.DAOSchemaSpec:
    if isinstance(spec, entities.DAOSchemaSpec):
        return spec
    return entities.DAOSchemaSpec.model_validate(spec)


def _default_position(index: int) -> ReactFlowPosition:
    column_count = 3
    x_spacing = 900.0
    y_spacing = 450.0

    col = index % column_count
    row = index // column_count

    return ReactFlowPosition(x=200.0 + col * x_spacing, y=200.0 + row * y_spacing)


def _convert_to_pascal(name: str) -> str:
    """Convert snake_case or kebab-case to PascalCase."""
    parts = [p for p in name.replace("-", "_").split("_") if p]
    return "".join(p[:1].upper() + p[1:] for p in parts)


def _node_height(row_count: int) -> int:
    return int(83 + 54 * row_count)


def _edge_id(source: str, source_handle: str, target: str, target_handle: str) -> str:
    return f"reactflow__edge-{source}{source_handle}-{target}{target_handle}"


def _edge_key(edge: ReactFlowEdge) -> tuple[str, int, str, int]:
    source_idx = int(edge.sourceHandle.split("-", 1)[1])
    target_idx = int(edge.targetHandle.split("-", 1)[1])
    a = (edge.source, source_idx)
    b = (edge.target, target_idx)
    (n1, i1), (n2, i2) = sorted([a, b])
    return (n1, i1, n2, i2)


def _build_property_index(nodes: list[ReactFlowNode]) -> dict[tuple[str, str], int]:
    index: dict[tuple[str, str], int] = {}
    for n in nodes:
        for i, p in enumerate(n.data.properties):
            index[(n.id, p.name)] = i
    return index


def _find_property_by_name(
    spec: entities.DAOSchemaSpec, prop_name: str
) -> typing.Optional[entities.DAOSchemaProperty]:
    for p in spec.properties:
        if p.name == prop_name:
            return p
    return None


def _find_primary_key_property(
    spec: entities.DAOSchemaSpec,
) -> entities.DAOSchemaProperty:
    for p in spec.properties:
        if p.key_type is not None and p.key_type.type == "primary_key":
            return p
    for p in spec.properties:
        if p.name == "id":
            return p
    return spec.properties[0]


def _stable_color(seed: str) -> str:
    digest = hashlib.md5(seed.encode("utf-8")).digest()
    r = 40 + digest[0] % 180
    g = 40 + digest[1] % 180
    b = 40 + digest[2] % 180
    return f"rgb({r}, {g}, {b})"


if __name__ == "__main__":
    dao_example = File("tests", "test_specs", "dao_spec.json").get_json()
    nodes, edges = convert_dao_spec_to_reactflow(dao_example)  # type: ignore
    print("Nodes:")
    for n in nodes:
        print(n)
    print("\nEdges:")
    for e in edges:
        print(e)
