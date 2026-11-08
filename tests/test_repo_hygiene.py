import json
import pathlib

import jsonschema

from devOS.domain import relational
from devOS.use_cases import generate_relational_contracts


def test_relational_contracts_match_their_canonical_model():
    frontend = pathlib.Path(__file__).parents[1] / "frontend/src"
    artifacts = generate_relational_contracts.GenerateRelationalContractsUseCase().execute()
    assert artifacts.json_schema == (frontend / "relational.schema.json").read_text(encoding="utf-8")
    assert artifacts.typescript == (frontend / "relational.types.ts").read_text(encoding="utf-8")
    assert json.loads(artifacts.json_schema) == relational.SchemaDocument.model_json_schema()
    jsonschema.Draft202012Validator.check_schema(json.loads(artifacts.json_schema))
