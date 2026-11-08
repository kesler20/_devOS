import os
import pathlib
import subprocess
import sys

from devOS.domain import relational
from devOS.use_cases import generate_relational_dao
from devOS.use_cases import generate_relational_sql


PROJECT = pathlib.Path(__file__).parents[1]
WIKI = PROJECT / "tests/fixtures/consumer_support/python"


def run_cli(root, *arguments):
    command = [sys.executable, "-c", "from devOS import main; main()", "build", *map(str, arguments)]
    return subprocess.run(command, cwd=root, capture_output=True, text=True)


def test_cli_checks_support_and_preserves_owned_outputs(tmp_path):
    document = PROJECT / "tests/fixtures/relational/valid-generation.json"
    destination = tmp_path / "src/consumer/dao.py"
    result = run_cli(tmp_path, "dao", document, "--output", destination)
    assert result.returncode == 0, result.stderr
    original = destination.read_bytes()
    assert run_cli(tmp_path, "dao", document, "--output", destination).returncode == 0
    assert destination.read_bytes() == original
    destination.write_text("# project-owned custom mappings\n")
    assert run_cli(tmp_path, "dao", document, "--output", destination).returncode == 1
    assert destination.read_text() == "# project-owned custom mappings\n"
    destination.write_bytes(original)
    blocked = tmp_path / "blocked"
    blocked.write_text("owned file")
    python_output = tmp_path / "src/consumer/dto.py"
    result = run_cli(tmp_path, "dto", "consumer.dao", "--python-output", python_output, "--typescript-output", blocked / "dto.ts")
    assert result.returncode == 1 and "Output parent" in result.stderr
    assert not python_output.exists()
    result = run_cli(tmp_path, "dto", "consumer.dao", "--python-output", python_output, "--typescript-output", python_output)
    assert result.returncode == 1 and "distinct paths" in result.stderr
    assert not python_output.exists()
    routes = tmp_path / "routes.py"
    result = run_cli(tmp_path, "api", "consumer.dao", "--dto-module", "consumer.dto", "--crud-module", "consumer.crud", "--session-module", "consumer.app", "--output", routes)
    assert result.returncode == 1 and "Install and adapt" in result.stderr
    assert not routes.exists()


def test_generated_pipeline_mounts_with_independently_installed_bundle(tmp_path, postgres_database):
    root = tmp_path / "src"
    consumer = root / "consumer"
    consumer.mkdir(parents=True)
    (consumer / "__init__.py").touch()
    document = relational.SchemaDocument.model_validate_json((PROJECT / "tests/fixtures/relational/valid.json").read_text())
    document.tables.extend([
        relational.Table.model_validate({"id": "lookup", "namespace_id": "ns", "name": {"name": "lookup"},
            "columns": [{"id": "lookup_code", "name": {"name": "code"}, "type": {"name": "text"}, "nullable": False},
                        {"id": "lookup_value", "name": {"name": "value"}, "type": {"name": "text"}, "nullable": False}],
            "constraints": [{"id": "lookup_pk", "kind": "primary_key", "column_ids": ["lookup_code"]}]}),
        relational.Table.model_validate({"id": "coded", "namespace_id": "ns", "name": {"name": "coded"},
            "columns": [{"id": "coded_code", "name": {"name": "code"}, "type": {"name": "text"}, "nullable": False},
                        {"id": "coded_sequence", "name": {"name": "sequence"}, "type": {"name": "integer"}, "nullable": False},
                        {"id": "coded_value", "name": {"name": "value"}, "type": {"name": "text"}, "nullable": True}],
            "constraints": [{"id": "coded_pk", "kind": "primary_key", "column_ids": ["coded_sequence", "coded_code"]}]}),
    ])
    (consumer / "dao.py").write_text(generate_relational_dao.GenerateRelationalDaoUseCase().execute(document))
    sql = generate_relational_sql.GenerateRelationalSqlUseCase().execute(document)
    with postgres_database.begin() as connection:
        connection.exec_driver_sql(sql)
    support = (WIKI / "crud/use_cases.py").read_text().replace("import adapters_clients.database.sql_database_adapter as database", "import consumer.database as database")
    (consumer / "crud.py").write_text(support)
    (consumer / "database.py").write_text((WIKI / "adapters_clients/database/sql_database_adapter.py").read_text())
    (consumer / "app.py").write_text('''import os
import sqlalchemy as sa
import sqlalchemy.orm as orm

engine = sa.create_engine(os.environ["CONSUMER_TEST_URL"])
def get_session():
    with orm.Session(engine) as session:
        yield session
''')
    before = {path.name: path.read_bytes() for path in consumer.glob("*.py") if path.name != "dao.py"}
    for _ in range(2):
        result = run_cli(tmp_path, "dto", "consumer.dao", "--python-output", consumer / "dto.py", "--typescript-output", tmp_path / "dto.ts")
        assert result.returncode == 0, result.stderr
        result = run_cli(tmp_path, "api", "consumer.dao", "--dto-module", "consumer.dto", "--crud-module", "consumer.crud", "--session-module", "consumer.app", "--output", consumer / "routes.py")
        assert result.returncode == 0, result.stderr
    assert all((consumer / name).read_bytes() == value for name, value in before.items())
    harness = '''
import sys
import uuid
from fastapi import FastAPI
from fastapi.testclient import TestClient
from consumer import routes, app as application

app = FastAPI()
app.include_router(routes.router)
tenant = str(uuid.uuid4())
child_id = str(uuid.uuid4())
with TestClient(app) as client:
    created = client.post('/parent', json={'entity': {'tenant_id': tenant, 'amount': '1234567890123456.1234', 'labels': ['a', None]}})
    assert created.status_code == 201, created.text
    parent = created.json()['entity']
    assert parent['amount'] == '1234567890123456.1234'
    assert parent['state'] == 'draft' and isinstance(parent['id'], str)
    path = '/parent/' + tenant + '/' + parent['id']
    assert client.get(path).json()['entity'] == parent
    assert len(client.get('/parent').json()['entities']) == 1
    assert client.patch(path, json={'entity': {}}).json()['entity']['amount'] == parent['amount']
    assert client.patch(path, json={'entity': {'amount': None}}).json()['entity']['amount'] is None
    assert client.patch(path, json={'entity': {'state': None}}).status_code == 422
    assert client.patch(path, json={'entity': {'id': '9'}}).status_code == 422
    assert client.post('/parent', json={'entity': {'tenant_id': tenant, 'id': '1'}}).status_code == 422
    assert client.get('/parent/not-uuid/1').status_code == 422
    assert client.get('/parent/' + tenant + '/9223372036854775808').status_code == 422
    assert client.post('/child', json={'entity': {'tenant_id': tenant, 'parent_id': parent['id'], 'id': child_id, 'payload': 'child'}}).status_code == 201
    assert client.get(path + '/relationships').json()['entity']['children'][0]['payload'] == 'child'
    assert client.get('/child/' + child_id + '/relationships').json()['entity']['parent']['id'] == parent['id']
    assert client.patch(path, json={'entity': {'amount': '-1'}}).status_code == 409
    assert client.get(path).status_code == 200
    assert client.delete(path).status_code == 200
    assert client.get('/child/' + child_id).status_code == 404
    assert client.get(path).status_code == 404
    assert client.patch(path, json={'entity': {}}).status_code == 404
    assert client.delete(path).status_code == 404
    lookup = client.post('/lookup', json={'entity': {'code': 'alpha beta', 'value': 'first'}})
    assert lookup.status_code == 201, lookup.text
    assert client.get('/lookup/alpha%20beta').json()['entity']['value'] == 'first'
    assert client.patch('/lookup/alpha%20beta', json={'entity': {'value': 'changed'}}).json()['entity']['value'] == 'changed'
    assert client.delete('/lookup/alpha%20beta').status_code == 200
    coded = client.post('/coded', json={'entity': {'code': 'alpha', 'sequence': 7, 'value': 'ordered'}})
    assert coded.status_code == 201, coded.text
    assert client.get('/coded/7/alpha').json()['entity']['value'] == 'ordered'
    assert client.get('/coded/alpha/7').status_code == 422
    assert client.get('/coded/2147483648/alpha').status_code == 422
    assert client.delete('/coded/7/alpha').status_code == 200
assert not any(name == 'devOS' or name.startswith('devOS.') or name.startswith('adapters_clients') for name in sys.modules)
application.engine.dispose()
'''
    result = subprocess.run([sys.executable, "-c", harness], cwd=tmp_path, env=dict(os.environ, PYTHONPATH=str(root), CONSUMER_TEST_URL=postgres_database.url.render_as_string(hide_password=False)), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    tests = tmp_path / "tests"
    tests.mkdir()
    result = run_cli(tmp_path, "tests", "contracts", "consumer.dao", "--dto-module", "consumer.dto", "--output", tests / "test_contracts.py")
    assert result.returncode == 0, result.stderr
    (tests / "conftest.py").write_text('''import uuid
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from consumer.routes import router

@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        yield client

@pytest.fixture
def resource_inputs(client):
    tenant = str(uuid.uuid4())
    seed = client.post('/parent', json={'entity': {'tenant_id': tenant}}).json()['entity']
    return {'Parent': {'tenant_id': str(uuid.uuid4()), 'amount': '1.2500'}, 'Child': {'tenant_id': tenant, 'parent_id': seed['id'], 'id': str(uuid.uuid4()), 'payload': 'payload'}, 'Lookup': {'code': str(uuid.uuid4()), 'value': 'value'}, 'Coded': {'code': str(uuid.uuid4()), 'sequence': 1, 'value': 'value'}}
''')
    result = subprocess.run([sys.executable, "-m", "pytest", str(tests), "-q", "--no-cov"], cwd=tmp_path, env=dict(os.environ, PYTHONPATH=str(root), CONSUMER_TEST_URL=postgres_database.url.render_as_string(hide_password=False)), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "4 passed" in result.stdout
