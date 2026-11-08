import json
import os
import pathlib
import shutil
import subprocess

import pydantic

from devOS.domain import relational
from devOS.use_cases import generate_relational_sql


def test_browser_and_python_agree_on_shared_fixtures(tmp_path):
    project = pathlib.Path(__file__).parents[1]
    frontend = project / "frontend"
    compiler = frontend / "node_modules/typescript/bin/tsc"
    node = shutil.which("node")
    assert node and compiler.is_file(), "Install Studio dependencies before running shared contract checks"
    subprocess.run([
        node, str(compiler), "--outDir", str(tmp_path), "--module", "commonjs",
        "--target", "es2020", "--skipLibCheck", "--strict",
        "src/relational.types.ts", "src/validateRelational.ts", "src/renderRelationalSql.ts", "src/relationalEditing.ts", "src/relationalDiagram.ts",
    ], cwd=frontend, check=True, capture_output=True, text=True)
    shutil.copyfile(frontend / "src/relational.schema.json", tmp_path / "relational.schema.json")
    fixtures = project / "tests/fixtures/relational"
    valid_documents = [json.loads(path.read_text()) for path in sorted(fixtures.glob("valid*.json"))]
    documents = list(valid_documents)
    documents.extend(json.loads(path.read_text())["document"] for path in sorted(fixtures.glob("invalid-*.json")))
    documents.extend([
        {},
        {"version": 1, "tables": []},
        {"version": True},
        {"version": "1"},
        {"version": 2},
    ])
    sequence_document = json.loads((fixtures / "valid-large-identity.json").read_text())
    for value in [9007199254740992, True, "9223372036854775808", "-9223372036854775809", "-0", "001", "1.5", "١"]:
        candidate = json.loads(json.dumps(sequence_document))
        candidate["tables"][0]["columns"][0]["identity"]["start"] = value
        documents.append(candidate)
    expected = []
    for document in documents:
        try:
            relational.SchemaDocument.model_validate(document)
            expected.append(True)
        except pydantic.ValidationError:
            expected.append(False)
    # Supply the normal frontend module search path to the isolated compilation.
    validation_file = tmp_path / "validateRelational.js"
    harness = """
const validate = require(process.argv[1]).validateRelational;
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(input.map(document => {
  try { validate(document); return true; }
  catch (error) { return false; }
})));
"""
    environment = dict(os.environ, NODE_PATH=str(frontend / "node_modules"))
    result = subprocess.run([node, "-e", harness, str(validation_file)], input=json.dumps(documents), capture_output=True, text=True, check=True, env=environment)
    assert json.loads(result.stdout) == expected
    render_harness = """
const render = require(process.argv[1]).renderRelationalSql;
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(input.map(render)));
"""
    result = subprocess.run([node, "-e", render_harness, str(tmp_path / "renderRelationalSql.js")], input=json.dumps(valid_documents), capture_output=True, text=True, check=True, env=environment)
    generator = generate_relational_sql.GenerateRelationalSqlUseCase()
    expected_sql = [generator.execute(relational.SchemaDocument.model_validate(value)) for value in valid_documents]
    assert json.loads(result.stdout) == expected_sql
    editing_harness = """
const assert = require('assert');
const edit = require(process.argv[1]);
const document = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const source = JSON.stringify(document);
const table = document.tables[0];
const amount = table.columns.find(column => column.id === 'amount');
const renamed = edit.replaceColumn(document, table.id, {...amount, name: {name: 'Total Amount', quoted: true}});
assert.equal(renamed.tables[0].columns.find(column => column.id === 'amount').name.name, 'Total Amount');
assert(renamed.tables[0].constraints.find(item => item.kind === 'check').expression.includes('"Total Amount"'));
assert.deepEqual(renamed.tables[1].constraints, document.tables[1].constraints);
assert.deepEqual(renamed.diagram, document.diagram);
assert.throws(() => edit.deleteColumn(document, table.id, 'amount'), /check references/);
assert.throws(() => edit.deleteColumn(document, table.id, 'tenant'), /outside/);
assert.throws(() => edit.deleteTable(document, table.id), /missing target table/);
assert.equal(JSON.stringify(document), source);
const order = table.columns.map(column => column.id).reverse();
const reordered = edit.reorderColumns(document, table.id, order);
assert.deepEqual(reordered.tables[0].columns.map(column => column.id), order);
assert.deepEqual(reordered.tables[1].constraints, document.tables[1].constraints);
assert.throws(() => edit.reorderColumns(document, table.id, []), /every owned column/);
const reopened = edit.openDocument(edit.exportDocument(renamed));
assert.deepEqual(reopened, renamed);
assert.throws(() => edit.openDocument('{"version":2}'));
assert.deepEqual(edit.openDocument(edit.exportDocument(document)), document);
const child = document.tables[1];
const updatedKey = {...child.constraints.find(item => item.id === 'child_fk'), on_update:'CASCADE'};
const withKey = edit.replaceConstraint(document, child.id, updatedKey);
assert.equal(withKey.tables[1].constraints.find(item => item.id === 'child_fk').on_update, 'CASCADE');
assert.deepEqual(withKey.tables[1].constraints.find(item => item.id === 'child_fk').column_ids, updatedKey.column_ids);
const withIndex = edit.replaceIndex(withKey, child.id, {id:'browser_index', name:{name:'payload_idx'}, column_ids:['payload'], method:'btree'});
assert.equal(withIndex.tables[1].indexes.find(item => item.id === 'browser_index').column_ids[0], 'payload');
const classAlias = edit.tableAlias(withIndex, table.id, 'ParentRecord');
const columnAlias = edit.columnAlias(classAlias, 'amount', 'total_amount');
const navigation = edit.relationshipConfiguration(columnAlias, {foreign_key_id:'child_fk', attribute_name:'owner', reverse_attribute_name:'records', cascade:'save-update, merge'});
assert.deepEqual(navigation.tables, withIndex.tables);
assert.deepEqual(navigation.diagram, withIndex.diagram);
assert.equal(edit.ormClassName(navigation, table), 'ParentRecord');
assert.equal(edit.ormAttributeName(navigation, amount), 'total_amount');
assert.equal(edit.navigationNames(navigation, child, updatedKey).attribute_name, 'owner');
assert.deepEqual(edit.openDocument(edit.exportDocument(navigation)), navigation);
assert.throws(() => edit.columnAlias(document, 'amount', 'metadata'));
const noFk = edit.deleteConstraint(document, child.id, 'child_fk');
const removed = edit.deleteTable(noFk, table.id);
assert.equal(removed.tables.length, 1);
assert(!removed.diagram.tables.some(item => item.table_id === table.id));
assert(!removed.orm.relationships.length);
assert(!removed.orm.tables.length);
"""
    edited = subprocess.run([node, "-e", editing_harness, str(tmp_path / "relationalEditing.js")], input=(fixtures / "valid.json").read_text(), capture_output=True, text=True, env=environment)
    assert edited.returncode == 0, edited.stderr
    graph_harness = """
const assert = require('assert');
const graph = require(process.argv[1]);
const edit = require(process.argv[2]);
const document = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const original = JSON.stringify(document);
const keys = document.tables.flatMap(table => table.constraints.filter(item => item.kind === 'foreign_key'));
const edges = graph.foreignKeyEdges(document);
assert.equal(edges.length, keys.length);
assert.equal(new Set(edges.map(edge => edge.id)).size, keys.length);
assert(edges.some(edge => edge.source === edge.target));
assert(edges.some(edge => edges.some(other => other.source === edge.target && other.target === edge.source && other.id !== edge.id)));
assert(edges.some(edge => edges.some(other => other.source === edge.source && other.target === edge.target && other.id !== edge.id && other.data.lane !== edge.data.lane)));
for (const edge of edges) {
    const key = keys.find(item => item.id === edge.id);
    assert.equal(edge.target, key.target_table_id);
    assert.equal(edge.sourceHandle, key.column_ids[0]);
    assert.equal(edge.targetHandle, key.target_column_ids[0]);
    assert.deepEqual(edge.data.constraint.column_ids, key.column_ids);
    assert.deepEqual(edge.data.constraint.target_column_ids, key.target_column_ids);
    assert.equal(edge.source, document.tables.find(table => table.constraints.includes(key)).id);
}
assert.equal(JSON.stringify(document), original);
const id = document.tables[0].id;
const moved = graph.moveTable(document, id, 137, 241);
assert.deepEqual(moved.tables, document.tables);
assert.deepEqual(graph.tablePosition(moved, id), {x:137, y:241});
const viewport = graph.setViewport(moved, 12, 18, 1.5);
assert.deepEqual(viewport.diagram.viewport, {x:12, y:18, zoom:1.5});
assert.deepEqual(edit.openDocument(edit.exportDocument(viewport)).diagram, viewport.diagram);
assert.throws(() => graph.moveTable(document, id, Infinity, 0));
assert.throws(() => graph.setViewport(document, 0, 0, 0));
assert.throws(() => edit.openDocument(JSON.stringify({...document, edges})));
const junction = document.tables.find(table => table.constraints.some(key => key.kind === 'primary_key' && key.column_ids.length === 3));
assert(junction.columns.some(column => column.name.name === 'position'));
assert.equal(graph.foreignKeyEdges(edit.openDocument(edit.exportDocument(document))).length, edges.length);
"""
    subprocess.run([node, "-e", graph_harness, str(tmp_path / "relationalDiagram.js"), str(tmp_path / "relationalEditing.js")], input=(fixtures / "valid-graph.json").read_text(), capture_output=True, text=True, check=True, env=environment)
