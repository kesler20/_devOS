import pathlib
import subprocess
import unittest.mock as mock

import pytest

from devOS.use_cases import config_project
from devOS.use_cases import use_cases
from devOS.use_cases.utils import file_io
from devOS.infrastructure import os_adapter
from devOS.infrastructure import scaffold_adapters


def test_context_aggregation_filters_and_orders_source_files(tmp_path):
    (tmp_path / "b.py").write_text("print('second')\n")
    (tmp_path / "a.ts").write_text("const first = 1;\n")
    (tmp_path / "ignored.md").write_text("Excluded")
    output = use_cases.AggregateContextUseCase().execute(".py,.ts", tmp_path)
    content = output.read_text()
    assert content.index("a.ts") < content.index("b.py")
    assert "Excluded" not in content
    assert "print('second')" in content


def test_docstring_formatting_uses_injected_process_boundary(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "src"
    nested.mkdir()
    monkeypatch.chdir(nested)
    runner = mock.Mock(return_value=subprocess.CompletedProcess([], 7))
    with pytest.raises(SystemExit) as outcome:
        use_cases.GenerateDocstringsUseCase(runner).execute()
    assert outcome.value.code == 7
    assert runner.call_args.kwargs["cwd"] == tmp_path
    assert b"NumPy" in runner.call_args.kwargs["input"]
    assert runner.call_args.args[0][-1] == "-"


def test_configuration_authoring_writes_valid_owned_settings(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "")
    console = os_adapter.OperatingSystemAdapter(str(tmp_path))
    feature = config_project.ConfigProjectUseCase(tmp_path, console, scaffold_adapters.GitProjectAdapter())
    result = feature.set_update_existing_config().execute()
    stored = tmp_path / "specs/project_config.json"
    assert result.project_name == tmp_path.name
    assert config_project.ConfigProjectUseCase(tmp_path, console, scaffold_adapters.GitProjectAdapter()).execute() == result
    assert stored.is_file()


def test_file_json_round_trip_preserves_unicode_and_nested_values(tmp_path):
    destination = file_io.File(tmp_path / "nested/config.json")
    destination.write_json({"label": "α", "items": [1, True, None]})
    assert destination.get_json() == {"label": "α", "items": [1, True, None]}
