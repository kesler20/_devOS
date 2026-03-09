from __future__ import annotations
import logging
import re
import typing
import pydantic
from devOS.domain import entities
from devOS.use_cases.utils.file_io import File


logger = logging.getLogger(__name__)


# ============================== #
#                                #
#   ReactFlow input structures   #
#                                #
# ============================== #


class ReactFlowEdge(pydantic.BaseModel):
    source: str
    target: str
    sourceHandle: typing.Optional[str] = None
    targetHandle: typing.Optional[str] = None

    model_config = pydantic.ConfigDict(extra="ignore")


class ReactFlowNode(pydantic.BaseModel):
    id: str
    data: dict[str, typing.Any]

    model_config = pydantic.ConfigDict(extra="ignore")


# ============================== #
#                                #
#   Public API                   #
#                                #
# ============================== #


def build_dao_spec(
    nodes: list[dict[str, typing.Any]],
    edges: list[dict[str, typing.Any]],
) -> list[entities.DAOSchemaSpec]:
    """
    Build DAO schema specs from a ReactFlow ORM builder export.

    This function:
    - Extracts DAO specs from node.data
    - Derives relationships from edges using row handles (e.g. "row-0")
    - Materializes one-to-many relationships by synthesizing:
        - parent.<children>: array + linked_property
        - child.<parent>: object + linked_property
        - child.<parent>_id: foreign_key + ondelete_cascade

    Parameters
    ----------
    nodes : list[dict[str, typing.Any]]
        ReactFlow nodes.
    edges : list[dict[str, typing.Any]]
        ReactFlow edges.

    Returns
    -------
    list[entities.DAOSchemaSpec]
        Validated DAO schema specs.

    Examples
    --------
    >>> import json
    >>> nodes = json.load(open("sample_node.json"))
    >>> edges = json.load(open("sample_edges.json"))
    >>> specs = build_dao_spec(nodes, edges)
    >>> isinstance(specs[0], entities.DAOSchemaSpec)
    True
    >>> [s.name for s in specs]
    ['Collection', 'Item']
    """
    parsed_nodes = [ReactFlowNode.model_validate(n) for n in nodes]
    parsed_edges = [ReactFlowEdge.model_validate(e) for e in edges]

    builder = _DAOSpecBuilder()
    return builder.build(parsed_nodes, parsed_edges)


# ============================== #
#                                #
#   Internal builder             #
#                                #
# ============================== #


class _DAOSpecBuilder:
    def build(
        self,
        nodes: list[ReactFlowNode],
        edges: list[ReactFlowEdge],
    ) -> list[entities.DAOSchemaSpec]:
        node_order = [n.id for n in nodes]

        association_node_ids: set[str] = set()
        regular_node_ids: set[str] = set()

        for n in nodes:
            is_assoc = bool((n.data or {}).get("is_association_table", False))
            if is_assoc:
                association_node_ids.add(n.id)
            else:
                regular_node_ids.add(n.id)

        specs_by_node_id: dict[str, dict[str, typing.Any]] = {}
        for n in nodes:
            specs_by_node_id[n.id] = _normalize_spec_from_node(n)

        assoc_tables_by_table_name: dict[str, dict[str, typing.Any]] = {}
        for node_id in association_node_ids:
            spec = specs_by_node_id.get(node_id)
            if spec:
                table_name = spec.get("table_name") or ""
                if table_name:
                    assoc_tables_by_table_name[table_name] = {
                        "node_id": node_id,
                        "spec": spec,
                    }

        for e in edges:
            source_spec = specs_by_node_id.get(e.source)
            target_spec = specs_by_node_id.get(e.target)
            if not source_spec or not target_spec:
                continue

            source_index = _parse_row_handle_index(e.sourceHandle)
            target_index = _parse_row_handle_index(e.targetHandle)
            if source_index is None or target_index is None:
                logger.debug("Skipping edge without row handles: %s", e.model_dump())
                continue

            source_prop = _get_prop_by_index(source_spec, source_index)
            target_prop = _get_prop_by_index(target_spec, target_index)
            if not source_prop or not target_prop:
                logger.debug(
                    "Skipping edge with out-of-range handle index: %s", e.model_dump()
                )
                continue

            source_is_assoc = e.source in association_node_ids
            target_is_assoc = e.target in association_node_ids

            if source_is_assoc and not target_is_assoc:
                _wire_association_fk_to_entity(
                    assoc_spec=source_spec,
                    assoc_prop=source_prop,
                    entity_spec=target_spec,
                    entity_prop=target_prop,
                )
                continue

            if target_is_assoc and not source_is_assoc:
                _wire_association_fk_to_entity(
                    assoc_spec=target_spec,
                    assoc_prop=target_prop,
                    entity_spec=source_spec,
                    entity_prop=source_prop,
                )
                continue

            self._apply_edge_relationship(
                left_spec=source_spec,
                left_prop=source_prop,
                right_spec=target_spec,
                right_prop=target_prop,
            )

        _attach_association_tables_to_entities(
            specs_by_node_id=specs_by_node_id,
            assoc_tables_by_table_name=assoc_tables_by_table_name,
            regular_node_ids=regular_node_ids,
        )

        output_specs: list[entities.DAOSchemaSpec] = []
        for node_id in node_order:
            if node_id in association_node_ids:
                continue
            spec_dict = specs_by_node_id.get(node_id)
            if not spec_dict:
                continue
            output_specs.append(entities.DAOSchemaSpec.model_validate(spec_dict))

        return output_specs

    def _apply_edge_relationship(
        self,
        left_spec: dict[str, typing.Any],
        left_prop: dict[str, typing.Any],
        right_spec: dict[str, typing.Any],
        right_prop: dict[str, typing.Any],
    ) -> None:
        left_type = (left_prop.get("type") or "").lower()
        right_type = (right_prop.get("type") or "").lower()

        left_is_m2m = left_type == "many_to_many"
        right_is_m2m = right_type == "many_to_many"
        if left_is_m2m or right_is_m2m:
            _materialize_many_to_many(
                left_spec=left_spec,
                left_prop=left_prop,
                right_spec=right_spec,
                right_prop=right_prop,
            )
            return

        left_is_many = _looks_like_many(left_prop)
        right_is_many = _looks_like_many(right_prop)

        one_side_many = left_is_many != right_is_many
        if one_side_many:
            parent_spec = left_spec if left_is_many else right_spec
            parent_many_prop = left_prop if left_is_many else right_prop
            child_spec = right_spec if left_is_many else left_spec

            _materialize_one_to_many(
                parent_spec=parent_spec,
                parent_many_prop=parent_many_prop,
                child_spec=child_spec,
            )
            return

        left_is_fk_to_pk = _looks_like_foreign_key(
            left_prop
        ) and _looks_like_primary_key(right_prop)
        if left_is_fk_to_pk:
            _wire_foreign_key(
                fk_owner_spec=left_spec, fk_prop=left_prop, referenced_spec=right_spec
            )
            return

        right_is_fk_to_pk = _looks_like_foreign_key(
            right_prop
        ) and _looks_like_primary_key(left_prop)
        if right_is_fk_to_pk:
            _wire_foreign_key(
                fk_owner_spec=right_spec, fk_prop=right_prop, referenced_spec=left_spec
            )
            return

        _link_props_bidirectional(left_spec, left_prop, right_spec, right_prop)


# ============================== #
#                                #
#   Relationship helpers         #
#                                #
# ============================== #


def _materialize_one_to_many(
    parent_spec: dict[str, typing.Any],
    parent_many_prop: dict[str, typing.Any],
    child_spec: dict[str, typing.Any],
) -> None:
    parent_name = parent_spec.get("name") or ""
    parent_table_name = parent_spec.get("table_name") or ""

    parent_many_prop["type"] = "array"
    if parent_many_prop.get("required") is None:
        parent_many_prop["required"] = False

    child_rel_name = _to_snake_case(parent_name)
    child_rel_prop = _get_or_create_property(
        child_spec,
        child_rel_name,
        default={
            "name": child_rel_name,
            "type": "object",
            "description": f"The {child_rel_name} this record belongs to.",
            "required": False,
        },
    )
    child_rel_prop["type"] = "object"
    if child_rel_prop.get("required") is None:
        child_rel_prop["required"] = False

    parent_pk = _find_primary_key(parent_spec)
    parent_pk_name = (parent_pk or {}).get("name") or "id"
    parent_pk_type = (parent_pk or {}).get("type") or "int"

    fk_name = f"{child_rel_name}_id"
    child_fk_prop = _get_or_create_property(
        child_spec,
        fk_name,
        default={
            "name": fk_name,
            "type": parent_pk_type,
            "description": f"Foreign key to {parent_table_name}.{parent_pk_name}.",
            "required": True,
        },
    )
    child_fk_prop["type"] = parent_pk_type
    if child_fk_prop.get("required") is None:
        child_fk_prop["required"] = True

    child_fk_prop["key_type"] = _merge_key_type(
        existing=child_fk_prop.get("key_type"),
        updates={
            "type": "foreign_key",
            "table": parent_table_name,
            "column": parent_pk_name,
            "behaviors": ["ondelete_cascade"],
        },
    )

    parent_many_prop["linked_property"] = _merge_linked_property(
        existing=parent_many_prop.get("linked_property"),
        updates={
            "table": child_spec.get("name"),
            "property": child_rel_prop.get("name"),
        },
    )
    child_rel_prop["linked_property"] = _merge_linked_property(
        existing=child_rel_prop.get("linked_property"),
        updates={
            "table": parent_spec.get("name"),
            "property": parent_many_prop.get("name"),
        },
    )


def _materialize_many_to_many(
    left_spec: dict[str, typing.Any],
    left_prop: dict[str, typing.Any],
    right_spec: dict[str, typing.Any],
    right_prop: dict[str, typing.Any],
) -> None:
    """Materialize a many-to-many relationship between two entities.

    Sets up the linked_property and many_to_many config on both sides.
    If one side already has M2M config, use that. Otherwise generate defaults.
    """
    left_name = left_spec.get("name") or ""
    right_name = right_spec.get("name") or ""
    left_table = left_spec.get("table_name") or ""
    right_table = right_spec.get("table_name") or ""

    left_m2m = left_prop.get("many_to_many") or {}
    right_m2m = right_prop.get("many_to_many") or {}

    is_self_referential = left_name == right_name

    association_table = (
        left_m2m.get("association_table")
        or right_m2m.get("association_table")
        or f"{_to_snake_case(left_name)}_{_to_snake_case(right_name)}"
    )

    left_prop["type"] = "many_to_many"
    left_prop["many_to_many"] = {
        "association_table": association_table,
        "self_referential": is_self_referential,
        "left_column": left_m2m.get("left_column"),
        "right_column": left_m2m.get("right_column"),
        "primaryjoin": left_m2m.get("primaryjoin"),
        "secondaryjoin": left_m2m.get("secondaryjoin"),
    }
    left_prop["linked_property"] = _merge_linked_property(
        existing=left_prop.get("linked_property"),
        updates={
            "table": right_name,
            "property": right_prop.get("name") or "",
        },
    )

    right_prop["type"] = "many_to_many"
    right_prop["many_to_many"] = {
        "association_table": association_table,
        "self_referential": is_self_referential,
        "left_column": right_m2m.get("left_column"),
        "right_column": right_m2m.get("right_column"),
        "primaryjoin": right_m2m.get("primaryjoin"),
        "secondaryjoin": right_m2m.get("secondaryjoin"),
    }
    right_prop["linked_property"] = _merge_linked_property(
        existing=right_prop.get("linked_property"),
        updates={
            "table": left_name,
            "property": left_prop.get("name") or "",
        },
    )


def _wire_foreign_key(
    fk_owner_spec: dict[str, typing.Any],
    fk_prop: dict[str, typing.Any],
    referenced_spec: dict[str, typing.Any],
) -> None:
    referenced_table_name = referenced_spec.get("table_name") or ""
    referenced_pk = _find_primary_key(referenced_spec)
    referenced_pk_name = (referenced_pk or {}).get("name") or "id"

    fk_prop["key_type"] = _merge_key_type(
        existing=fk_prop.get("key_type"),
        updates={
            "type": "foreign_key",
            "table": referenced_table_name,
            "column": referenced_pk_name,
            "behaviors": ["ondelete_cascade"],
        },
    )


def _link_props_bidirectional(
    left_spec: dict[str, typing.Any],
    left_prop: dict[str, typing.Any],
    right_spec: dict[str, typing.Any],
    right_prop: dict[str, typing.Any],
) -> None:
    left_prop["linked_property"] = _merge_linked_property(
        existing=left_prop.get("linked_property"),
        updates={
            "table": right_spec.get("name"),
            "property": right_prop.get("name"),
        },
    )
    right_prop["linked_property"] = _merge_linked_property(
        existing=right_prop.get("linked_property"),
        updates={
            "table": left_spec.get("name"),
            "property": left_prop.get("name"),
        },
    )


def _wire_association_fk_to_entity(
    assoc_spec: dict[str, typing.Any],
    assoc_prop: dict[str, typing.Any],
    entity_spec: dict[str, typing.Any],
    entity_prop: dict[str, typing.Any],
) -> None:
    """Wire a foreign key from an association table to an entity's primary key."""
    entity_table_name = entity_spec.get("table_name") or ""
    entity_pk = _find_primary_key(entity_spec)
    entity_pk_name = (entity_pk or {}).get("name") or "id"

    assoc_prop["key_type"] = _merge_key_type(
        existing=assoc_prop.get("key_type"),
        updates={
            "type": "foreign_key",
            "table": entity_table_name,
            "column": entity_pk_name,
            "behaviors": ["ondelete_cascade"],
        },
    )


def _attach_association_tables_to_entities(
    specs_by_node_id: dict[str, dict[str, typing.Any]],
    assoc_tables_by_table_name: dict[str, dict[str, typing.Any]],
    regular_node_ids: set[str],
) -> None:
    """Attach association tables to the entities that reference them via M2M properties."""
    assoc_tables_by_class_name: dict[str, dict[str, typing.Any]] = {}
    for table_name, info in assoc_tables_by_table_name.items():
        class_name = (info.get("spec") or {}).get("name") or ""
        if class_name:
            assoc_tables_by_class_name[class_name] = info
            assoc_tables_by_class_name[f"{class_name}.__table__"] = info

    for node_id in regular_node_ids:
        spec = specs_by_node_id.get(node_id)
        if not spec:
            continue

        association_tables: list[dict[str, typing.Any]] = []
        added_tables: set[str] = set()

        properties = spec.get("properties") or []
        for prop in properties:
            prop_type = (prop.get("type") or "").lower()
            if prop_type != "many_to_many":
                continue

            m2m_config = prop.get("many_to_many") or {}
            assoc_table_ref = m2m_config.get("association_table") or ""
            if not assoc_table_ref:
                continue

            assoc_info = assoc_tables_by_table_name.get(
                assoc_table_ref
            ) or assoc_tables_by_class_name.get(assoc_table_ref)
            if not assoc_info:
                continue

            assoc_spec = assoc_info.get("spec") or {}
            actual_table_name = assoc_spec.get("table_name") or assoc_table_ref

            if actual_table_name in added_tables:
                continue

            assoc_props = assoc_spec.get("properties") or []

            columns: list[dict[str, typing.Any]] = []
            for assoc_prop in assoc_props:
                key_type = assoc_prop.get("key_type") or {}
                if key_type.get("type") != "foreign_key":
                    continue

                behaviors = key_type.get("behaviors") or []
                ondelete = "CASCADE"
                for b in behaviors:
                    if b.startswith("ondelete_"):
                        ondelete = b.replace("ondelete_", "").upper()
                        break

                columns.append(
                    {
                        "name": assoc_prop.get("name") or "",
                        "type": assoc_prop.get("type") or "int",
                        "foreign_key_table": key_type.get("table") or "",
                        "foreign_key_column": key_type.get("column") or "id",
                        "ondelete": ondelete,
                        "primary_key": True,
                    }
                )

            if columns:
                class_name = assoc_spec.get("name")
                association_tables.append(
                    {
                        "table_name": actual_table_name,
                        "class_name": (
                            class_name
                            if class_name != _to_pascal(actual_table_name)
                            else None
                        ),
                        "columns": columns,
                    }
                )
                added_tables.add(actual_table_name)
                logger.info(
                    "Attached association table %s to entity %s",
                    actual_table_name,
                    spec.get("name"),
                )

        if association_tables:
            spec["association_tables"] = association_tables


def _to_pascal(name: str) -> str:
    """Convert snake_case to PascalCase."""
    parts = [p for p in name.replace("-", "_").split("_") if p]
    return "".join(p[:1].upper() + p[1:] for p in parts)


# ============================== #
#                                #
#   Spec normalization            #
#                                #
# ============================== #


def _normalize_spec_from_node(node: ReactFlowNode) -> dict[str, typing.Any]:
    data = node.data or {}

    name = (data.get("name") or "").strip()
    table_name = (data.get("table_name") or "").strip()
    description = data.get("description")

    raw_props: list[dict[str, typing.Any]] = list(data.get("properties") or [])
    properties: list[dict[str, typing.Any]] = []

    for p in raw_props:
        normalized = dict(p)

        prop_name = _normalize_identifier(normalized.get("name") or "")
        normalized["name"] = prop_name

        linked = normalized.get("linked_property")
        if isinstance(linked, dict):
            raw_linked_property = (linked.get("property") or "").strip()
            if raw_linked_property:
                linked_property_name = _normalize_identifier(raw_linked_property)
            else:
                linked_property_name = ""
            linked["property"] = linked_property_name
            normalized["linked_property"] = linked

        key_type = normalized.get("key_type")
        if isinstance(key_type, dict):
            normalized["key_type"] = _sanitize_key_type_dict(key_type)

        many_to_many = normalized.get("many_to_many")
        if isinstance(many_to_many, dict):
            normalized["many_to_many"] = _sanitize_many_to_many_dict(many_to_many)

        properties.append(normalized)

    unique_constraints = data.get("unique_constraints") or []

    return {
        "name": name,
        "table_name": table_name,
        "description": description,
        "properties": properties,
        "unique_constraints": unique_constraints,
    }


def _sanitize_key_type_dict(key_type: dict[str, typing.Any]) -> dict[str, typing.Any]:
    kt = dict(key_type)
    kt_type = (kt.get("type") or "").strip()

    behaviors = kt.get("behaviors")
    behaviors_list: list[str] = list(behaviors or [])

    if kt_type == "primary_key":
        # Remove on-delete behaviors from primary keys
        behaviors_list = [
            b
            for b in behaviors_list
            if b not in ("ondelete_cascade", "ondelete_set_null", "ondelete_restrict")
        ]
        if "auto_increment" not in behaviors_list:
            behaviors_list.append("auto_increment")

    if kt_type == "foreign_key":
        # Ensure at least one on-delete behavior exists
        has_ondelete = any(
            b in behaviors_list
            for b in ("ondelete_cascade", "ondelete_set_null", "ondelete_restrict")
        )
        if not has_ondelete:
            behaviors_list.append("ondelete_cascade")

    kt["behaviors"] = behaviors_list
    return kt


def _sanitize_many_to_many_dict(
    many_to_many: dict[str, typing.Any]
) -> dict[str, typing.Any]:
    """Sanitize and normalize a many_to_many configuration dict."""
    m2m = dict(many_to_many)

    association_table = (m2m.get("association_table") or "").strip()
    m2m["association_table"] = association_table

    self_referential = bool(m2m.get("self_referential", False))
    m2m["self_referential"] = self_referential

    left_column = m2m.get("left_column")
    if left_column:
        m2m["left_column"] = str(left_column).strip()

    right_column = m2m.get("right_column")
    if right_column:
        m2m["right_column"] = str(right_column).strip()

    primaryjoin = m2m.get("primaryjoin")
    if primaryjoin:
        m2m["primaryjoin"] = str(primaryjoin).strip()

    secondaryjoin = m2m.get("secondaryjoin")
    if secondaryjoin:
        m2m["secondaryjoin"] = str(secondaryjoin).strip()

    return m2m


# ============================== #
#                                #
#   Low-level utilities          #
#                                #
# ============================== #


_ROW_HANDLE_RE = re.compile(r"row[-_:](\d+)", re.IGNORECASE)


def _parse_row_handle_index(handle: typing.Optional[str]) -> typing.Optional[int]:
    if not handle:
        return None

    match = _ROW_HANDLE_RE.search(handle)
    if not match:
        return None

    index = int(match.group(1))
    if index < 0:
        return None

    return index


def _get_prop_by_index(
    spec: dict[str, typing.Any], index: int
) -> typing.Optional[dict[str, typing.Any]]:
    props: list[dict[str, typing.Any]] = list(spec.get("properties") or [])
    if index < 0 or index >= len(props):
        return None
    return props[index]


def _get_or_create_property(
    spec: dict[str, typing.Any],
    prop_name: str,
    default: dict[str, typing.Any],
) -> dict[str, typing.Any]:
    props: list[dict[str, typing.Any]] = list(spec.get("properties") or [])
    spec["properties"] = props

    for p in props:
        if p.get("name") == prop_name:
            return p

    props.append(default)
    return default


def _find_primary_key(
    spec: dict[str, typing.Any]
) -> typing.Optional[dict[str, typing.Any]]:
    props: list[dict[str, typing.Any]] = list(spec.get("properties") or [])

    for p in props:
        key_type = p.get("key_type") or {}
        if isinstance(key_type, dict) and key_type.get("type") == "primary_key":
            return p

    for p in props:
        if p.get("name") == "id":
            return p

    if props:
        return props[0]

    return None


def _looks_like_primary_key(prop: dict[str, typing.Any]) -> bool:
    if prop.get("name") == "id":
        return True
    key_type = prop.get("key_type")
    if isinstance(key_type, dict) and key_type.get("type") == "primary_key":
        return True
    return False


def _looks_like_foreign_key(prop: dict[str, typing.Any]) -> bool:
    name = prop.get("name") or ""
    if isinstance(name, str) and name.endswith("_id"):
        return True
    key_type = prop.get("key_type")
    if isinstance(key_type, dict) and key_type.get("type") == "foreign_key":
        return True
    return False


def _looks_like_many(prop: dict[str, typing.Any]) -> bool:
    prop_type = (prop.get("type") or "").lower()
    if prop_type == "array":
        return True

    name = prop.get("name") or ""
    if not isinstance(name, str):
        return False

    if name.endswith("_id"):
        return False

    return False


def _merge_key_type(
    existing: typing.Optional[dict[str, typing.Any]],
    updates: dict[str, typing.Any],
) -> dict[str, typing.Any]:
    merged: dict[str, typing.Any] = dict(existing or {})
    merged.update({k: v for k, v in updates.items() if k != "behaviors"})

    existing_behaviors = list((existing or {}).get("behaviors") or [])
    update_behaviors = list(updates.get("behaviors") or [])

    merged_behaviors = []
    for b in existing_behaviors + update_behaviors:
        if b not in merged_behaviors:
            merged_behaviors.append(b)

    if merged_behaviors:
        merged["behaviors"] = merged_behaviors

    return merged


def _merge_linked_property(
    existing: typing.Optional[dict[str, typing.Any]],
    updates: dict[str, typing.Any],
) -> dict[str, typing.Any]:
    """Merge linked_property, preserving cascade, order_by, and foreign_key."""
    merged: dict[str, typing.Any] = dict(existing or {})
    # Only update table and property from updates
    if "table" in updates:
        merged["table"] = updates["table"]
    if "property" in updates:
        merged["property"] = updates["property"]
    # Preserve existing cascade, order_by, foreign_key if not in updates
    for field in ("cascade", "order_by", "foreign_key"):
        if field in updates and updates[field] is not None:
            merged[field] = updates[field]
        elif field not in merged:
            merged[field] = None
    return merged


def _normalize_identifier(value: str) -> str:
    v = (value or "").strip().lower()
    v = v.replace("-", "_").replace(" ", "_")
    v = re.sub(r"[^a-z0-9_]", "", v)

    if not v:
        raise ValueError("Encountered empty/invalid identifier")

    if v[0].isdigit():
        v = f"field_{v}"

    if not v.isidentifier():
        raise ValueError(f"Invalid identifier after normalization: {v!r}")

    return v


def _to_snake_case(name: str) -> str:
    n = (name or "").strip()
    n = n.replace("-", "_").replace(" ", "_")
    n = re.sub(r"(?<!^)(?=[A-Z])", "_", n)
    return _normalize_identifier(n)


if __name__ == "__main__":
    nodes = File("tests", "samples", "sample_nodes.json").get_json()
    edges = File("tests", "samples", "sample_edges.json").get_json()
    specs = build_dao_spec(nodes, edges)  # type: ignore
    for spec in specs:
        print(spec.model_dump_json(indent=2))
