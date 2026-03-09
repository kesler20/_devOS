import typing
import devOS.domain.entities as entities


def generate_boxed_block_comment(title: str, *, pad: int = 3) -> str:
    """
    Produces:

    # ========== #
    #            #
    #   TITLE    #
    #            #
    # ========== #
    """
    label = title.strip().upper()
    inner_width = max(len(label) + (pad * 2), 18)
    top = f"# {'=' * inner_width} #"
    empty = f"# {' ' * inner_width} #"
    mid = f"# {label.center(inner_width)} #"
    return f"\n{top}\n{empty}\n{mid}\n{empty}\n{top}\n\n"


def generate_tag_block_comment(tag: str) -> str:
    return generate_boxed_block_comment(f"{tag.strip().upper()} ENDPOINTS")


def get_field_type_from_spec(field_spec: entities.EndpointFieldSpec) -> str:
    t = (field_spec.type or "").lower()
    if t == "dao":
        assert field_spec.name
        base = f"dto.{field_spec.name}Read"
        return f"typing.List[{base}]" if field_spec.is_list else base
    return entities.convert_type_py(field_spec.type)


def generate_schema_for_request(
    endpoint: entities.EndpointSpec,
    language: str | None = None,
) -> tuple[list[dict[str, typing.Any]], list[dict[str, typing.Any]]]:
    """
    Returns (path_fields, body_fields) with elements:
      {name,type,required,description}

    Parameters
    ----------
    endpoint : entities.EndpointSpec
        The endpoint specification.
    language : str, optional
        If provided, only include fields that have no language restriction
        or include this language in their language list.
    """
    rs = endpoint.request_schema or {}

    path_fields: list[dict[str, typing.Any]] = []
    body_fields: list[dict[str, typing.Any]] = []
    for field_name, field_spec in rs.items():
        field_matches_language = (
            field_spec.language is None
            or language is None
            or language in field_spec.language
        )
        if not field_matches_language:
            continue
        # Use field_spec.name if provided, otherwise use the dictionary key
        actual_field_name = field_spec.name if field_spec.name else field_name
        item = {
            "name": actual_field_name,
            "type": get_field_type_from_spec(field_spec),
            "required": bool(field_spec.required),
            "description": field_spec.description,
        }
        (path_fields if field_spec.parse_value_from_path else body_fields).append(item)
    return (path_fields, body_fields)


def generate_schema_block_comment(title: str) -> str:
    return generate_boxed_block_comment(title)


def generate_schema_tag_block_comment(tag: str) -> str:
    return generate_schema_block_comment(f"{tag.strip().upper()} SCHEMAS")


def render_pydantic_field_line(
    name: str,
    typ: str,
    required: bool,
    description: typing.Optional[str],
) -> str:
    # NOTE: returns source code line(s); caller is responsible for importing pydantic/typing
    if required:
        if description:
            return (
                f'    {name}: {typ} = pydantic.Field(..., description="{description}")'
            )
        return f"    {name}: {typ} = pydantic.Field(...)"
    else:
        if description:
            return f'    {name}: typing.Optional[{typ}] = pydantic.Field(None, description="{description}")'
        return f"    {name}: typing.Optional[{typ}] = pydantic.Field(None)"


def merge_implied_path_params_into_path_fields(
    endpoint_path: str,
    path_fields: list[dict[str, typing.Any]],
) -> list[dict[str, typing.Any]]:
    implied = entities.extract_path_params(endpoint_path)
    by_name = {f["name"]: f for f in path_fields}
    for p in implied:
        if p not in by_name:
            by_name[p] = {
                "name": p,
                "type": "str",
                "required": True,
                "description": None,
            }
    return list(by_name.values())
