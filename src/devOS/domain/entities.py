from __future__ import annotations
import pydantic
import typing
import enum

# =========================== #
#                             #
#   Spec validation helpers   #
#                             #
# =========================== #


def assert_no_spaces(value: str, what: str) -> str:
    if " " in value:
        raise ValueError(f"{what} must not contain spaces: {value!r}")
    return value


def assert_identifier(value: str, what: str) -> str:
    if not value.isidentifier():
        raise ValueError(f"{what} must be a valid python identifier: {value!r}")
    return value


def assert_lowercase(value: str, what: str) -> str:
    if value.lower() != value:
        raise ValueError(f"{what} must be lowercase: {value!r}")
    return value


def extract_path_params(path: str) -> set[str]:
    params: set[str] = set()
    for part in str(path).split("{")[1:]:
        params.add(part.split("}", 1)[0])
    return {p for p in params if p}


def convert_to_pascal(name: str) -> str:
    parts = [p for p in name.replace("-", "_").split("_") if p]
    return "".join(p[:1].upper() + p[1:] for p in parts)


def convert_type_py(t: str) -> str:
    t = (t or "").lower()
    if t in {"string", "str", "text"}:
        return "str"
    if t in {"int", "integer"}:
        return "int"
    if t in {"float", "number"}:
        return "float"
    if t in {"bool", "boolean"}:
        return "bool"
    return "typing.Any"


# ========================= #
#                           #
#   DAO SPECIFICATION       #
#                           #
# ========================= #


class DAOSchemaLinkedProperty(pydantic.BaseModel):
    """Describe a linked property relationship in a DAO schema.

    Attributes
    ----------
    table : str
        Name of the related table.
    property : str
        Name of the related property.
    cascade : str, optional
        Cascade behavior for the relationship (e.g., "all, delete-orphan").
    order_by : str, optional
        Order by clause for the relationship (e.g., "Question.order.asc()").
    foreign_key : str, optional
        Foreign key expression as-is (e.g., "Question.questionnaire_id").
    """

    table: str
    property: str
    cascade: typing.Optional[str] = None
    order_by: typing.Optional[str] = None
    foreign_key: typing.Optional[str] = None

    @pydantic.field_validator("table")
    @classmethod
    def _validate_table(cls, v: str) -> str:
        v = v.strip()
        assert_no_spaces(v, "linked_property.table")
        assert_identifier(v, "linked_property.table")
        return v

    @pydantic.field_validator("property")
    @classmethod
    def _validate_property(cls, v: str) -> str:
        v = v.strip()
        # Allow empty property name for many-to-many without back_populates
        if not v:
            return v
        assert_no_spaces(v, "linked_property.property")
        assert_identifier(v, "linked_property.property")
        assert_lowercase(v, "linked_property.property")
        return v


class DAOSchemaKeyType(pydantic.BaseModel):
    """Define key type metadata for a DAO schema property.

    Attributes
    ----------
    type : str
        Key type identifier.
    table : str, optional
        Related table name, if applicable.
    column : str, optional
        Related column name, if applicable.
    behaviors : list[str], optional
        Additional key behaviors.
    """

    type: str
    table: typing.Optional[str] = None
    column: typing.Optional[str] = None
    behaviors: typing.Optional[list[str]] = None


class DAOSchemaManyToManyConfig(pydantic.BaseModel):
    """Configuration for many-to-many relationships.

    Attributes
    ----------
    association_table : str
        Name of the association table.
    self_referential : bool
        Whether this is a self-referential relationship.
    left_column : str, optional
        Column name for this side in the association table.
    right_column : str, optional
        Column name for the other side in the association table.
    primaryjoin : str, optional
        Custom primaryjoin expression for self-referential relationships.
    secondaryjoin : str, optional
        Custom secondaryjoin expression for self-referential relationships.
    """

    association_table: str
    self_referential: bool = False
    left_column: typing.Optional[str] = None
    right_column: typing.Optional[str] = None
    primaryjoin: typing.Optional[str] = None
    secondaryjoin: typing.Optional[str] = None


class DAOSchemaProperty(pydantic.BaseModel):
    """Define a property within a DAO schema.

    Attributes
    ----------
    name : str
        Property name.
    type : str
        Property type (int, str, text, bool, float, datetime, enum, array, object, many_to_many).
    description : str, optional
        Human-readable description for the property.
    required : bool, optional
        Whether the property is required.
    default_value : str, optional
        Default value for the column, written as-is in the generated code.
    enum_name : str, optional
        Name of the enum type for enum columns (e.g., "QuestionnaireStatus").
    key_type : DAOSchemaKeyType, optional
        Key type metadata for the property.
    linked_property : DAOSchemaLinkedProperty, optional
        Linked property information for one-to-many/one-to-one relationships.
    many_to_many : DAOSchemaManyToManyConfig, optional
        Configuration for many-to-many relationships.
    """

    name: str
    type: str
    description: typing.Optional[str] = None
    required: typing.Optional[bool] = None
    default_value: typing.Optional[str] = None
    enum_name: typing.Optional[str] = None
    key_type: typing.Optional[DAOSchemaKeyType] = None
    linked_property: typing.Optional[DAOSchemaLinkedProperty] = None
    many_to_many: typing.Optional[DAOSchemaManyToManyConfig] = None

    @pydantic.field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        v = v.strip()
        assert_no_spaces(v, "property.name")
        assert_identifier(v, "property.name")
        assert_lowercase(v, "property.name")
        return v


class DAOSchemaEnumMember(pydantic.BaseModel):
    """Define a member of an enum.

    Attributes
    ----------
    key : str
        The enum member key/name (e.g., "DRAFT", "ACTIVE").
    value : str
        The enum member value (e.g., "draft", "active").
    """

    key: str
    value: str

    @pydantic.field_validator("key")
    @classmethod
    def _validate_key(cls, v: str) -> str:
        v = v.strip()
        assert_no_spaces(v, "enum.key")
        assert_identifier(v, "enum.key")
        return v


class DAOSchemaEnum(pydantic.BaseModel):
    """Define an enum type for use in DAO properties.

    Attributes
    ----------
    name : str
        Enum class name (e.g., "QuestionnaireStatus").
    members : list[DAOSchemaEnumMember]
        List of enum members with key-value pairs.
    description : str, optional
        Human-readable description for the enum.
    """

    name: str
    members: list[DAOSchemaEnumMember]
    description: typing.Optional[str] = None

    @pydantic.field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        v = v.strip()
        assert_no_spaces(v, "enum.name")
        assert_identifier(v, "enum.name")
        return v


class DAOSchemaAssociationColumn(pydantic.BaseModel):
    """Define a column in an association table.

    Attributes
    ----------
    name : str
        Column name.
    type : str
        Column type.
    foreign_key_table : str
        Table that this column references.
    foreign_key_column : str
        Column that this column references.
    ondelete : str, optional
        ON DELETE behavior (CASCADE, SET NULL, RESTRICT).
    primary_key : bool
        Whether this column is part of the primary key.
    """

    name: str
    type: str = "int"
    foreign_key_table: str
    foreign_key_column: str = "id"
    ondelete: typing.Optional[str] = "CASCADE"
    primary_key: bool = True


class DAOSchemaAssociationTable(pydantic.BaseModel):
    """Define an association table for many-to-many relationships.

    Attributes
    ----------
    table_name : str
        Name of the association table.
    class_name : str, optional
        If provided, generates an explicit class instead of sqlalchemy.Table.
    columns : list[DAOSchemaAssociationColumn]
        Columns in the association table.
    extra_properties : list[DAOSchemaProperty], optional
        Additional properties for association class (only if class_name is set).
    unique_constraints : list[list[str]], optional
        List of unique constraints, each as a list of column names.
    """

    table_name: str
    class_name: typing.Optional[str] = None
    columns: list[DAOSchemaAssociationColumn]
    extra_properties: typing.Optional[list[DAOSchemaProperty]] = None
    unique_constraints: typing.Optional[list[list[str]]] = None


class DAOSchemaSpec(pydantic.BaseModel):
    """Represent the complete DAO schema definition.

    Attributes
    ----------
    name : str
        Class name for the generated DAO.
    table_name : str
        Database table name.
    description : str, optional
        Human-readable description for the DAO.
    properties : list[DAOSchemaProperty]
        Properties included in the schema.
    association_tables : list[DAOSchemaAssociationTable], optional
        Association tables for many-to-many relationships owned by this entity.
    unique_constraints : list[list[str]], optional
        List of unique constraints, each as a list of column names.
    enums : list[DAOSchemaEnum], optional
        Enum definitions used by this DAO's properties.
    imports : list[str], optional
        Custom imports to add to the generated DAO file header.
    """

    name: str
    table_name: str
    description: typing.Optional[str] = None
    properties: list[DAOSchemaProperty]
    association_tables: typing.Optional[list[DAOSchemaAssociationTable]] = None
    unique_constraints: typing.Optional[list[list[str]]] = None
    enums: typing.Optional[list[DAOSchemaEnum]] = None
    imports: typing.Optional[list[str]] = None

    @pydantic.field_validator("name")
    @classmethod
    def _validate_class_name(cls, v: str) -> str:
        v = v.strip()
        assert_no_spaces(v, "spec.name (class name)")
        assert_identifier(v, "spec.name (class name)")
        return v


# ========================= #
#                           #
#   Endpoint spec models    #
#                           #
# ========================= #


class EndpointFieldSpec(pydantic.BaseModel):
    """Define a field in an endpoint request or response schema.

    Attributes
    ----------
    type : str
        Field type identifier.
    description : str, optional
        Human-readable description for the field.
    required : bool
        Whether the field is required.
    parse_value_from_path : bool
        Whether to parse the value from the URL path.
    business_rules : list[str], optional
        Business rules associated with the field.
    name : str, optional
        Field name override for generated code. For DAO types, specifies the entity name.
        For other types, overrides the field name from the schema key.
    is_list : bool
        Whether the field represents a list value.
    language : list[SupportedLanguagesValues], optional
        Languages this field should be generated for.
    """

    type: str
    description: typing.Optional[str] = None
    required: bool = False
    parse_value_from_path: bool = False
    business_rules: typing.Optional[list[str]] = None
    name: typing.Optional[str] = None
    is_list: bool = False
    language: typing.Optional[list[SupportedLanguagesValues]] = None

    @pydantic.model_validator(mode="after")
    def _validate_dao_fields(self) -> EndpointFieldSpec:
        t = (self.type or "").lower()
        if t == "dao":
            if not self.name:
                raise ValueError('FieldSpec with type="dao" must include a "name"')
        if self.name:
            assert_no_spaces(self.name, "field name override")
            assert_identifier(self.name, "field name override")
        return self


class EndpointUseCaseSpec(pydantic.BaseModel):
    """Describe the use case handling an endpoint.

    Attributes
    ----------
    name : str
        Use case class name.
    method : str
        Method name on the use case.
    """

    name: str
    method: str

    @pydantic.field_validator("name", "method")
    @classmethod
    def _v_ident(cls, v: str) -> str:
        v = v.strip()
        assert_no_spaces(v, "use_case field")
        assert_identifier(v, "use_case field")
        return v


class EndpointSpec(pydantic.BaseModel):
    """Define an API endpoint specification.

    Attributes
    ----------
    name : str
        Endpoint name.
    description : str, optional
        Human-readable description of the endpoint.
    method : str
        HTTP method for the endpoint.
    version : str
        API version.
    path : str
        Route path template.
    request_schema : dict[str, EndpointFieldSpec], optional
        Request schema fields keyed by name.
    response_schema : dict[str, EndpointFieldSpec], optional
        Response schema fields keyed by name.
    use_case : EndpointUseCaseSpec
        Use case invocation details.
    language : list[SupportedLanguagesValues], optional
        Languages this endpoint should be generated for.
    """

    name: str
    description: typing.Optional[str] = None
    method: str = "GET"
    version: str = "v1"
    path: str
    request_schema: typing.Optional[dict[str, EndpointFieldSpec]] = None
    response_schema: typing.Optional[dict[str, EndpointFieldSpec]] = None
    use_case: EndpointUseCaseSpec
    language: typing.Optional[list[SupportedLanguagesValues]] = None

    @pydantic.field_validator("name")
    @classmethod
    def _v_endpoint_name(cls, v: str) -> str:
        v = v.strip()
        assert_no_spaces(v, "endpoint.name")
        assert_identifier(v, "endpoint.name")
        assert_lowercase(v, "endpoint.name")
        return v

    @pydantic.model_validator(mode="after")
    def _validate_request_schema_keys_and_path(self) -> "EndpointSpec":
        params = extract_path_params(self.path)

        if self.request_schema:
            for fname, fs in self.request_schema.items():
                assert_no_spaces(fname, f"endpoint.{self.name}.request_schema key")
                assert_identifier(fname, f"endpoint.{self.name}.request_schema key")
                assert_lowercase(fname, f"endpoint.{self.name}.request_schema key")
                if fs.parse_value_from_path and fname not in params:
                    raise ValueError(
                        f"endpoint {self.name!r}: field {fname!r} has parse_value_from_path=True "
                        f"but is not present in path params {sorted(params)!r}"
                    )

        if self.response_schema:
            for fname in self.response_schema.keys():
                assert_no_spaces(fname, f"endpoint.{self.name}.response_schema key")
                assert_identifier(fname, f"endpoint.{self.name}.response_schema key")
                assert_lowercase(fname, f"endpoint.{self.name}.response_schema key")

        return self


class EndpointsSpec(pydantic.BaseModel):
    """Aggregate endpoint specifications for a service.

    Attributes
    ----------
    title : str
        Service title.
    version : str
        API version.
    description : str, optional
        Human-readable description of the service.
    endpoints : dict[str, list[EndpointSpec]]
        Endpoints grouped by resource name.
    include_relationship_endpoints : bool, optional
        Whether to include relationship endpoints.
    """

    title: str
    version: str
    description: typing.Optional[str] = None
    endpoints: dict[str, list[EndpointSpec]]
    include_relationship_endpoints: typing.Optional[bool] = False


# ======================= #
#                         #
#   PROJECT CONFIG SPEC   #
#                         #
# ======================= #


class SupportedLanguages(enum.Enum):
    TYPESCRIPT = "typescript"
    PYTHON = "python"


SupportedLanguagesValues = typing.Literal["typescript", "python"]


class CodeGenOutputConfig(pydantic.BaseModel):
    """
    Specify code generation output settings for a project.

    Parameters
    ----------
    directory : list[str]
        Path to the output directory, relative to the project root, as a list of path components.
    language : SupportedLanguagesValues
        Programming language to use for generated code.
    """

    directory: list[str]
    language: SupportedLanguagesValues


class ProjectSpecificConfig(pydantic.BaseModel):
    """
    Project-specific configuration for code generation outputs.

    Parameters
    ----------
    dao_output_config : CodeGenOutputConfig
        Output configuration for DAO code.
    dto_output_config : CodeGenOutputConfig
        Output configuration for DTO code.
    api_output_config : CodeGenOutputConfig
        Output configuration for API code.
    test_api_output_config : list[CodeGenOutputConfig]
        Output configuration for API test code.
    test_services_output_directory : list[str]
        Output configuration for service test code.
    adapters_output_directory : list[str]
        Output directory for adapter code, relative to the project root, as a list of path components
    use_cases_output_directory : list[str]
        Output directory for use case code, relative to the project root, as a list of path components.
    app_definition_directory : list[str]
        Output directory for fastapi app definition code and `get_db`, relative to the project root, as a list of path components.
    """

    dao_output_config: list[CodeGenOutputConfig]
    dto_output_config: list[CodeGenOutputConfig]
    api_output_config: list[CodeGenOutputConfig]
    test_api_output_config: list[CodeGenOutputConfig]
    test_services_output_directory: list[str]
    adapters_output_directory: list[str] = []
    use_cases_output_directory: list[str] = []
    app_definition_directory: list[str] = []


class HomeRootConfig(pydantic.BaseModel):
    """
    Global configuration using the user's home directory as the root.

    Parameters
    ----------
    snippets : list[str]
        Paths to snippet directories, specified as lists of path components, relative to the user's home directory.
    vault : list[str]
        Path to the credentials vault, specified as a list of path components, relative to the user's home directory.
    """

    snippets: list[str]
    vault: list[str]


class ProjectConfigSchema(pydantic.BaseModel):
    """
    Overall project configuration schema.

    Parameters
    ----------
    home_root : HomeRootConfig
        Global configuration rooted at the user's home directory.
    project_root : ProjectSpecificConfig
        Project-specific configuration, with paths relative to the project root.
    """

    home_root: HomeRootConfig
    project_root: ProjectSpecificConfig
