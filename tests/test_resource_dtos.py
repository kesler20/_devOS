import datetime
import decimal
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import uuid

import pydantic
import pytest
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg
import sqlalchemy.orm as orm

from devOS.domain import resource_schema
from devOS.use_cases import generate_resource_dtos


@pytest.fixture
def contracts(tmp_path):
    class Base(orm.DeclarativeBase):
        pass

    class SampleDAO(Base):
        __tablename__ = "sample"
        id = sa.Column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
        code = sa.Column(sa.String(3), nullable=False)
        amount = sa.Column(sa.Numeric(30, 8), nullable=False)
        count = sa.Column(sa.Integer, nullable=False, server_default="7")
        active = sa.Column(sa.Boolean, nullable=True)
        token = sa.Column(sa.Uuid, nullable=True)
        state = sa.Column(sa.Enum("draft", "active"), nullable=True)
        labels = sa.Column(pg.ARRAY(sa.String), nullable=True)
        matrix = sa.Column(pg.ARRAY(sa.Integer, dimensions=2), nullable=True)
        date = sa.Column(sa.Date, nullable=True)
        time = sa.Column(sa.Time, nullable=True)
        timestamp = sa.Column(sa.DateTime, nullable=True)
        duration = sa.Column(pg.INTERVAL, nullable=True)
        data = sa.Column(sa.LargeBinary, nullable=True)
        settings = sa.Column(sa.JSON, nullable=True)

    result = generate_resource_dtos.GenerateResourceDtosUseCase().execute([resource_schema.MappedResource(SampleDAO.__mapper__)])
    path = tmp_path / "dto.py"
    path.write_text(result.python)
    spec = importlib.util.spec_from_file_location("sample_dto", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module, SampleDAO, result
    Base.registry.dispose()


def test_write_patch_and_read_preserve_omission_null_and_precision(contracts):
    dto, dao, _ = contracts
    write = dto.SampleWrite(code="abc", amount="1234567890123456789012.12345678")
    assert write.model_dump(exclude_unset=True) == {"code": "abc", "amount": "1234567890123456789012.12345678"}
    assert dto.SamplePatch(active=None).model_fields_set == {"active"}
    for payload in [{"id": "1"}, {"amount": None}, {"count": None}, {"unknown": True}]:
        with pytest.raises(pydantic.ValidationError):
            dto.SamplePatch.model_validate(payload)
    with pytest.raises(pydantic.ValidationError):
        dto.SampleWrite(code="abc", amount="1", id="1")
    row = dao(id=9223372036854775807, code="abc", amount=decimal.Decimal("12.34567890"), count=7, token=uuid.UUID(int=1), date=datetime.date(2026, 10, 12), data=b"abc", duration=datetime.timedelta(seconds=90))
    payload = dto.SampleRead.model_validate(row).model_dump(mode="json")
    assert payload["id"] == "9223372036854775807"
    assert payload["amount"] == "12.34567890"
    assert payload["data"] == "YWJj"
    assert payload["token"] == str(uuid.UUID(int=1))
    assert payload["date"] == "2026-10-12"
    assert payload["duration"] == "PT1M30S"


def test_python_and_zod_accept_the_same_wire_payloads(contracts, tmp_path):
    dto, _, generated = contracts
    frontend = pathlib.Path(__file__).parents[1] / "frontend"
    # Resolve TypeScript dependencies from the installed Studio package.
    source = frontend / "src/.test-resource-dtos.ts"
    source.write_text(generated.typescript)
    node = shutil.which("node")
    try:
        subprocess.run([node, str(frontend / "node_modules/typescript/bin/tsc"), str(source), "--outDir", str(tmp_path), "--module", "commonjs", "--target", "es2020", "--skipLibCheck", "--strict", "--esModuleInterop"], cwd=frontend, check=True, capture_output=True, text=True)
    finally:
        source.unlink()
    base = {"code": "abc", "amount": "1234567890123456789012.12345678"}
    cases = [base, {}, {**base, "id": "1"}]
    changes = [
        {"code": "abcd"}, {"code": "😀😀😀"}, {"code": 1}, {"amount": 1}, {"amount": "NaN"},
        {"count": 1.0}, {"count": True}, {"count": "1"}, {"count": 2147483648}, {"count": None},
        {"active": None}, {"active": 1}, {"state": "draft"}, {"state": "missing"},
        {"labels": ["a", None]}, {"labels": [1]}, {"matrix": [[1, None], [2, 3]]}, {"matrix": [[1], [2, 3]]},
        {"date": "2024-02-29"}, {"date": "2023-02-29"}, {"date": "0000-01-01"},
        {"time": "12:30:45+01:00"}, {"time": "25:00:00"},
        {"timestamp": "2026-10-12T12:30:45Z"}, {"timestamp": "2026-10-12T12:30:45"},
        {"timestamp": "2026-10-12T12:30Z"}, {"duration": "PT1M30S"}, {"duration": "P"},
        {"data": "YWJj"}, {"data": "abc"}, {"token": str(uuid.UUID(int=1))}, {"token": "x"},
        {"settings": {"a": [1, True, None]}}, {"unknown": 1},
    ]
    cases.extend({**base, **change} for change in changes)
    roles = {"SampleWrite": cases, "SamplePatch": changes, "SampleIdentity": [{"id": "1"}, {"id": "9223372036854775807"}, {"id": "9223372036854775808"}, {"id": 1}, {"id": "١"}]}
    expected = {}
    for name, payloads in roles.items():
        expected[name] = []
        for payload in payloads:
            try:
                getattr(dto, name).model_validate(payload)
                expected[name].append(True)
            except pydantic.ValidationError:
                expected[name].append(False)
    harness = "const dto=require(process.argv[1]); const cases=JSON.parse(require('fs').readFileSync(0,'utf8')); process.stdout.write(JSON.stringify(Object.fromEntries(Object.entries(cases).map(([name,values])=>[name,values.map(value=>dto[name+'Schema'].safeParse(value).success)]))));"
    result = subprocess.run([node, "-e", harness, str(tmp_path / ".test-resource-dtos.js")], input=json.dumps(roles), capture_output=True, text=True, check=True, env=dict(os.environ, NODE_PATH=str(frontend / "node_modules")))
    assert json.loads(result.stdout) == expected
