import pathlib
from devOS.infrastructure import os_adapter, scaffold_adapters

import devOS.use_cases.config_project as config_project


def test_project_name_is_persisted_without_git_metadata(
    tmp_path: pathlib.Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    project_config = config_project.ConfigProjectUseCase(tmp_path, os_adapter.OperatingSystemAdapter(str(tmp_path)), scaffold_adapters.GitProjectAdapter()).execute()

    assert project_config.project_name == tmp_path.name
