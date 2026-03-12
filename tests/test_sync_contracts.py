import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from devOS.domain import entities
from devOS.use_cases.code_gen.contracts.sync_contracts import SyncContractsUseCase


def _build_project_config(
    source_language: entities.SupportedLanguagesValues,
    output_directory: list[str],
) -> entities.ProjectConfigSchema:
    return entities.ProjectConfigSchema(
        home_root=entities.HomeRootConfig(snippets=["snippets"], vault=["vault"]),
        project_root=entities.ProjectSpecificConfig(
            dao_output_config=[],
            dto_output_config=[],
            api_output_config=[],
            test_api_output_config=[],
            test_services_output_directory=["tests"],
            adapters_output_directory=[],
            use_cases_output_directory=[],
            app_definition_directory=[],
            contract_sync_output_config=[
                entities.ContractSyncOutputConfig(
                    source_language=source_language,
                    output_directory=output_directory,
                )
            ],
        ),
    )


def test_sync_python_contract_to_typescript(
    tmp_path: pathlib.Path, monkeypatch
) -> None:
    source_file = tmp_path / "src" / "contracts" / "models.py"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text(
        """# @contract
import pydantic

class User(pydantic.BaseModel):
    name: str
    age: int | None = None
    tags: list[str] = []
""",
        encoding="utf-8",
    )

    project_config = _build_project_config("python", ["out", "typescript"])
    monkeypatch.chdir(tmp_path)

    SyncContractsUseCase(project_structure=project_config).execute()

    generated_file = tmp_path / "out" / "typescript" / "models.ts"
    assert generated_file.exists()
    generated_content = generated_file.read_text(encoding="utf-8")

    assert "export const UserSchema = z.object({" in generated_content
    assert "name: z.string()," in generated_content
    assert "age: z.number().optional()," in generated_content
    assert "tags: z.array(z.string()).optional()," in generated_content


def test_sync_typescript_contract_to_python(
    tmp_path: pathlib.Path, monkeypatch
) -> None:
    source_file = tmp_path / "src" / "contracts" / "types.ts"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text(
        """// @contract
import { z } from 'zod';

export const UserSchema = z.object({
  id: z.string(),
  rating: z.number().optional(),
  active: z.boolean(),
  tags: z.array(z.string()),
});
""",
        encoding="utf-8",
    )

    project_config = _build_project_config("typescript", ["out", "python"])
    monkeypatch.chdir(tmp_path)

    SyncContractsUseCase(project_structure=project_config).execute()

    generated_file = tmp_path / "out" / "python" / "types.py"
    assert generated_file.exists()
    generated_content = generated_file.read_text(encoding="utf-8")

    assert "class User(pydantic.BaseModel):" in generated_content
    assert "id: str" in generated_content
    assert "rating: float | None = None" in generated_content
    assert "active: bool" in generated_content
    assert "tags: list[str]" in generated_content


def test_sync_python_contract_without_properties_skips_output(
    tmp_path: pathlib.Path, monkeypatch
) -> None:
    source_file = tmp_path / "src" / "contracts" / "empty_model.py"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text(
        """# @contract
import pydantic

class EmptyModel(pydantic.BaseModel):
    pass
""",
        encoding="utf-8",
    )

    project_config = _build_project_config("python", ["out", "typescript"])
    monkeypatch.chdir(tmp_path)

    SyncContractsUseCase(project_structure=project_config).execute()

    generated_file = tmp_path / "out" / "typescript" / "empty_model.ts"
    assert generated_file.exists() is False


def test_sync_typescript_contract_without_properties_skips_output(
    tmp_path: pathlib.Path, monkeypatch
) -> None:
    source_file = tmp_path / "src" / "contracts" / "empty_types.ts"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text(
        """// @contract
import { z } from 'zod';

export const EmptySchema = z.object({});
""",
        encoding="utf-8",
    )

    project_config = _build_project_config("typescript", ["out", "python"])
    monkeypatch.chdir(tmp_path)

    SyncContractsUseCase(project_structure=project_config).execute()

    generated_file = tmp_path / "out" / "python" / "empty_types.py"
    assert generated_file.exists() is False
